"""Unit tests for app/dao/purchase_order.py.

Implements tests/unit/dao/purchase_order.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture).

Patched: only the clock of the `AL` cards (Conventions, Externals: clock(L, U)
patches the std `datetime.datetime`, `app.dao.purchase_order.utcnow` with
`create=True` and `app.utils.time.utcnow`). Race simulations: AL-29 / AL-30
patch `app.dao.purchase_order._po_number_taken` (`create=True`). Nothing else
is mocked.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`, naive datetimes, and the Decimal strings as carded)
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.status import Status
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao"
dao = purchase_order_dao
idao = purchase_order_item_dao

# Convention "MISSING"
MISSING = 999999999

# Convention "T0", "T1 ... T5" (naive UTC), "DAY", "D1"
T0 = datetime(2026, 3, 1, 8, 0)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)
T3 = datetime(2026, 3, 4, 11, 0)
T4 = datetime(2026, 3, 4, 12, 0)
T5 = datetime(2026, 3, 4, 13, 0)
DAY = date(2026, 3, 4)
D1 = date(2026, 1, 5)

# Convention "An AL card without a clock line runs under clock(2031-06-01 12:00, same)"
Y2031 = datetime(2031, 6, 1, 12, 0)

# Bug titles for the xfail reasons (docs/testing/bugs.md)
B2630 = "BUG-2630: PO numbers skip numbers another workspace already uses"
B2632 = "BUG-2632: PO number's year comes from the server's local clock"
B2633 = "BUG-2633: PO hub search text acts as SQL wildcards"
B2634 = "BUG-2634: PO hub search matches a deleted supplier's name"
B2635 = "BUG-2635: PO hub recent and pending samples show never-edited orders first"
B2636 = "BUG-2636: PO hub oldest drafts top 5 has unordered ties"
B2637 = "BUG-2637: PO found for an invoice is arbitrary when two POs share it"
B2638 = "BUG-2638: PO hub item-name preview has unordered ties"
B2639 = "BUG-2639: PO hub money totals add voided orders and count them as open"
B2640 = "BUG-2640: PO outstanding payment filter includes orders whose invoice is a draft or voided"
B2641 = "BUG-2641: PO list's received progress ignores refunded quantity"


def xid(k):
    """Convention "XID(k)"."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def high_id(db, table):
    """Convention "HIGH_ID(t)": max(greatest id or 0, last_value of <t>_id_seq) + 1000001."""
    max_id = db.scalar(text(f"SELECT coalesce(max(id), 0) FROM {table}"))
    last_value = db.scalar(text(f"SELECT last_value FROM {table}_id_seq"))
    return max(max_id, last_value) + 1000001


# --------------------------------------------------------------------------- #
# Conventions -> Externals: clock(L, U)
# --------------------------------------------------------------------------- #


@contextmanager
def clock(local=Y2031, utc=Y2031):
    """Convention "clock(L, U)": std `datetime.datetime.now()` returns L; both
    `app.dao.purchase_order.utcnow` (create=True) and `app.utils.time.utcnow` return U."""

    class _Fake(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return local

    with (
        patch("datetime.datetime", _Fake),
        patch("app.dao.purchase_order.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def _invoice(db, ws, account, **cols):
    """Convention "invoice of Wk" (with the columns after "but")."""
    fields = {
        "workspace_id": ws.id,
        "account_id": account.id,
        "invoice_type": "payable",
        "invoice_status": "confirmed",
        "payment_status": "unpaid",
        "invoice_amount": Decimal("100.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": D1,
        "allow_payments": True,
    }
    fields.update(cols)
    return _add(db, AccountInvoice(**fields))


def _stages(db, ws):
    return [
        _add(db, Status(workspace_id=ws.id, name=n, comment="po stage"))
        for n in ("Draft", "Planning", "Receiving", "Complete")
    ]


def _item(db, ws, name, norm, unit):
    return _add(
        db, Item(workspace_id=ws.id, name=name, name_normalized=norm, unit=unit)
    )


# Convention "Standing rows" 1-4, in their order. `s.W1`, `s.SP1`, `s.V2`, ...
@pytest.fixture
def s(db):
    r = SimpleNamespace()
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2, r.U3 = make_profile(db), make_profile(db), make_profile(db)
    # step 2: W0
    r.SD0, r.SP0, r.SR0, r.SC0 = _stages(db, r.W0)
    r.A0 = _add(db, Account(workspace_id=r.W0.id, name="Northwind West"))
    r.F0 = _add(
        db, Factory(workspace_id=r.W0.id, name="Main Plant", abbreviation="MP0")
    )
    r.I0 = _item(db, r.W0, "Bolt", "bolt", "pcs")
    r.V0 = _invoice(db, r.W0, r.A0)
    # step 3: W1
    r.SD1, r.SP1, r.SR1, r.SC1 = _stages(db, r.W1)
    r.AL1 = _add(db, Account(workspace_id=r.W1.id, name="Alpha Parts"))
    r.A1 = _add(db, Account(workspace_id=r.W1.id, name="Northwind Traders"))
    r.AH1 = _add(db, Account(workspace_id=r.W1.id, name="Zenith Tools"))
    r.FA = _add(
        db, Factory(workspace_id=r.W1.id, name="Alpha Plant", abbreviation="AP")
    )
    r.F1 = _add(db, Factory(workspace_id=r.W1.id, name="Main Plant", abbreviation="MP"))
    r.FZ = _add(db, Factory(workspace_id=r.W1.id, name="Zeta Plant", abbreviation="ZP"))
    r.MA = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.FA.id, name="Press A"))
    r.M1 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F1.id, name="Press 1"))
    r.MZ = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.FZ.id, name="Press Z"))
    r.PJA = _add(
        db,
        Project(
            workspace_id=r.W1.id,
            factory_id=r.FA.id,
            name="Project A",
            description="Main",
        ),
    )
    r.PJ1 = _add(
        db,
        Project(
            workspace_id=r.W1.id,
            factory_id=r.F1.id,
            name="Project 1",
            description="Main",
        ),
    )
    r.PJZ = _add(
        db,
        Project(
            workspace_id=r.W1.id,
            factory_id=r.FZ.id,
            name="Project Z",
            description="Main",
        ),
    )
    r.CA = _add(
        db, ProjectComponent(workspace_id=r.W1.id, project_id=r.PJA.id, name="Part A")
    )
    r.C1 = _add(
        db, ProjectComponent(workspace_id=r.W1.id, project_id=r.PJ1.id, name="Part 1")
    )
    r.CZ = _add(
        db, ProjectComponent(workspace_id=r.W1.id, project_id=r.PJZ.id, name="Part Z")
    )
    r.I1 = _item(db, r.W1, "Bolt", "bolt", "pcs")
    r.IN1 = _item(db, r.W1, "Nut", "nut", "pcs")
    r.IK = _item(db, r.W1, "Steel", "steel", "kg")
    r.IW = _item(db, r.W1, "Washer", "washer", "pcs")
    r.IR = _item(db, r.W1, "Rivet", "rivet", "pcs")
    r.IE = _item(db, r.W1, "", "", "pcs")
    r.V1 = _invoice(db, r.W1, r.A1)
    r.V2 = _invoice(db, r.W1, r.A1)
    r.V3 = _invoice(db, r.W1, r.A1)
    # step 4: W2
    r.SD2, r.SP2, r.SR2, r.SC2 = _stages(db, r.W2)
    r.A2 = _add(db, Account(workspace_id=r.W2.id, name="Northwind East"))
    r.F2 = _add(
        db, Factory(workspace_id=r.W2.id, name="Main Plant", abbreviation="MP2")
    )
    r.I9 = _item(db, r.W2, "Bolt", "bolt", "pcs")
    r.V9 = _invoice(db, r.W2, r.A2)
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def inv1(db, s, **cols):
    """An extra "invoice of W1, but <cols>" (OQ37 rows VP, VD, VX, VXP, VL, VPA, VO)."""
    return _invoice(db, s.W1, s.A1, **cols)


def _po_fields(s, number):
    return {
        "workspace_id": s.W1.id,
        "po_number": number,
        "account_id": s.A1.id,
        "destination_type": "storage",
        "destination_id": s.F1.id,
        "subtotal": Decimal("0.00"),
        "total_amount": Decimal("0.00"),
        "current_status_id": s.SD1.id,
        "created_by": s.U1.id,
        "created_at": T3,
    }


def po(db, s, number, **cols):
    """Convention "po N" (W1); `cols` = the columns after "but" (`id="HIGH"` for HIGH_ID)."""
    fields = _po_fields(s, number)
    fields.update(cols)
    if fields.get("id") == "HIGH":
        fields["id"] = high_id(db, "purchase_orders")
    return _add(db, PurchaseOrder(**fields))


def po0(db, s, number, **cols):
    """Convention "po of W0 N" (W0, A0, F0, SD0)."""
    base = {
        "workspace_id": s.W0.id,
        "account_id": s.A0.id,
        "destination_id": s.F0.id,
        "current_status_id": s.SD0.id,
    }
    return po(db, s, number, **{**base, **cols})


def po2(db, s, number, **cols):
    """Convention "po of W2 N" (W2, A2, F2, SD2)."""
    base = {
        "workspace_id": s.W2.id,
        "account_id": s.A2.id,
        "destination_id": s.F2.id,
        "current_status_id": s.SD2.id,
    }
    return po(db, s, number, **{**base, **cols})


def stage(st):
    """Convention "stage S"."""
    return {"current_status_id": st.id}


def closed(s):
    """Convention "closed" (W1)."""
    return {"current_status_id": s.SC1.id, "paid": True}


def voided(s):
    """Convention "voided"."""
    return {
        "voided": True,
        "voided_at": T4,
        "voided_by": s.U1.id,
        "void_note": "Entered twice",
    }


def edited(s, at):
    """Convention "edited at T"."""
    return {"updated_at": at, "updated_by": s.U1.id}


# Convention "no supplier"
NO_SUPPLIER = {"account_id": None}


def to_machine(m):
    """Convention "to machine M"."""
    return {"destination_type": "machine", "destination_id": m.id}


def to_component(c):
    """Convention "to component C"."""
    return {"destination_type": "project", "destination_id": c.id}


def to_storage(f):
    """Convention "to storage F"."""
    return {"destination_type": "storage", "destination_id": f.id}


def closed_account(s):
    """Convention "closed account" (also "deleted machine")."""
    return {
        "is_deleted": True,
        "is_active": False,
        "deleted_at": T0,
        "deleted_by": s.U1.id,
    }


def deleted_project(s):
    """Convention "deleted project"."""
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": s.U1.id}


def pos(db, s, n):
    """Convention "pos(n)": returns R, where R[k] is the row `PO-2026-<k+1>`."""
    rows = []
    for k in range(n):
        row = PurchaseOrder(
            workspace_id=s.W1.id,
            po_number=f"PO-2026-{k + 1:03d}",
            account_id=s.A1.id,
            destination_type="storage",
            destination_id=s.F1.id,
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            current_status_id=s.SD1.id,
            created_by=s.U1.id,
            created_at=T0 + timedelta(minutes=k),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def line(db, s, order, number, **cols):
    """Convention "line of O" with `line_number`; `cols` = the columns after "but"
    (`id="HIGH"` for HIGH_ID)."""
    item = {s.W0.id: s.I0, s.W2.id: s.I9}.get(order.workspace_id, s.I1)
    fields = {
        "workspace_id": order.workspace_id,
        "purchase_order_id": order.id,
        "line_number": number,
        "item_id": item.id,
        "quantity_ordered": Decimal("1.00"),
        "quantity_received": Decimal("0.00"),
    }
    fields.update(cols)
    if fields.get("id") == "HIGH":
        fields["id"] = high_id(db, "purchase_order_items")
    return _add(db, PurchaseOrderItem(**fields))


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def bump_p(db, x):
    """Convention "bumpP(X)"."""
    db.execute(
        text("UPDATE purchase_orders SET po_number = po_number WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


def bump_l(db, x):
    """Convention "bumpL(X)"."""
    db.execute(
        text("UPDATE purchase_order_items SET notes = notes WHERE id = :i"), {"i": x.id}
    )
    db.expire_all()


def edit_pending(db, s, o1):
    """Convention "edit + pending": O1 edited (not flushed), P added (not flushed). Returns P."""
    o1.total_amount = Decimal("5.00")
    p = PurchaseOrder(**_po_fields(s, "PO-2026-950"))
    db.add(p)
    return p


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


def eids(lst):
    return [e["id"] for e in lst]


def reread_po(db, x_id):
    """Convention "re-read X" for a PO."""
    db.expire_all()
    return db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == x_id))


def totals(db):
    """Convention "nothing written": pocount and the purchase_order_items count."""
    return (
        db.scalar(select(func.count()).select_from(PurchaseOrder)),
        db.scalar(select(func.count()).select_from(PurchaseOrderItem)),
    )


def order_part(sql):
    """Convention "order_part": text after the first ORDER BY, before any LIMIT."""
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


class Recorder:
    """Convention "Statement recorder": every statement (and its parameters) sent while open."""

    def __init__(self, db):
        self.bind = db.get_bind()
        self.calls = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.calls.append((statement, parameters))

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    @property
    def sqls(self):
        return [st for st, _ in self.calls if st.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [
            st
            for st, _ in self.calls
            if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]

    @property
    def sql(self):
        """First SELECT reading `FROM purchase_orders` (dao cards)."""
        return next(st for st in self.sqls if "FROM purchase_orders" in st)

    @property
    def isql(self):
        """First SELECT reading `FROM purchase_order_items` (idao cards)."""
        return next(st for st in self.sqls if "FROM purchase_order_items" in st)

    def selects_with_param(self, value):
        out = []
        for st, params in self.calls:
            if not st.lstrip().upper().startswith("SELECT"):
                continue
            values = params.values() if isinstance(params, dict) else (params or ())
            if value in values:
                out.append(st)
        return out


def hub(db, ws, **filters):
    """Every `HF` card: `dao.list_for_hub(db, workspace_id=..., limit=1000, ...)`."""
    return dao.list_for_hub(db, workspace_id=ws.id, limit=1000, **filters)


# =========================================================================== #
# _apply_purchase_order_hub_filters (through list_for_hub)
# =========================================================================== #


# [claude] PUO-HF-01
def test_puo_hf_01__only_w1_pos(db, s):
    """PUO-HF-01 — only W1's POs, with the same number in W0 and W2.
    Rules: _apply… R1; Model facts (uq_po_workspace_number)."""
    po0(db, s, "PO-2026-001")
    o1 = po(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-001")
    result = hub(db, s.W1)
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-02
def test_puo_hf_02__asked_for_w2(db, s):
    """PUO-HF-02 — asked for W2, only W2's PO, though W0 and W1 POs come earlier.
    Rules: _apply… R1."""
    po0(db, s, "PO-2026-001")
    po(db, s, "PO-2026-001")
    x2 = po2(db, s, "PO-2026-001")
    result = hub(db, s.W2)
    # Then 1
    assert idset(result) == {x2.id}


# [claude] PUO-HF-03
def test_puo_hf_03__asked_for_w0(db, s):
    """PUO-HF-03 — asked for W0, only W0's PO, though W1 and W2 POs come later.
    Rules: _apply… R1."""
    x0 = po0(db, s, "PO-2026-001")
    po(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-001")
    result = hub(db, s.W0)
    # Then 1
    assert idset(result) == {x0.id}


# [claude] PUO-HF-04
def test_puo_hf_04__account_filter(db, s):
    """PUO-HF-04 — account filter keeps that supplier only, with a lower and a higher account id beside it.
    Rules: _apply… R2."""
    po(db, s, "PO-2026-101", account_id=s.AL1.id)
    o2 = po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103", account_id=s.AH1.id)
    po(db, s, "PO-2026-104", **NO_SUPPLIER)
    result = hub(db, s.W1, account_id=s.A1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-05
def test_puo_hf_05__account_id_zero_matches_nothing(db, s):
    """PUO-HF-05 — account_id 0 is a filter that matches nothing.
    Rules: _apply… R2."""
    po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **NO_SUPPLIER)
    result = hub(db, s.W1, account_id=0)
    # Then 1
    assert result == []


# [claude] PUO-HF-06
def test_puo_hf_06__account_id_none_is_no_filter(db, s):
    """PUO-HF-06 — account_id None is no filter.
    Rules: _apply… R2."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **NO_SUPPLIER)
    result = hub(db, s.W1, account_id=None)
    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] PUO-HF-07
def test_puo_hf_07__invoice_filter(db, s):
    """PUO-HF-07 — invoice filter keeps POs of that invoice, with a lower and a higher invoice beside it.
    Rules: _apply… R2."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    o2 = po(db, s, "PO-2026-102", invoice_id=s.V2.id)
    po(db, s, "PO-2026-103", invoice_id=s.V3.id)
    po(db, s, "PO-2026-104")
    result = hub(db, s.W1, invoice_id=s.V2.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-08
def test_puo_hf_08__invoice_id_zero_matches_nothing(db, s):
    """PUO-HF-08 — invoice_id 0 is a filter that matches nothing.
    Rules: _apply… R2."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po(db, s, "PO-2026-102")
    result = hub(db, s.W1, invoice_id=0)
    # Then 1
    assert result == []


# [claude] PUO-HF-09
def test_puo_hf_09__date_from_from_midnight(db, s):
    """PUO-HF-09 — date_from keeps the day from 00:00:00, not the microsecond before.
    Rules: _apply… R3."""
    po(db, s, "PO-2026-101", created_at=datetime(2026, 3, 3, 23, 59, 59, 999999))
    o2 = po(db, s, "PO-2026-102", created_at=datetime(2026, 3, 4, 0, 0, 0))
    o3 = po(db, s, "PO-2026-103", created_at=datetime(2026, 3, 9, 12, 0, 0))
    result = hub(db, s.W1, date_from=DAY)
    # Then 1
    assert idset(result) == {o2.id, o3.id}


# [claude] PUO-HF-10
def test_puo_hf_10__date_to_whole_end_day(db, s):
    """PUO-HF-10 — date_to keeps the whole end day, to 23:59:59.999999, not the next midnight.
    Rules: _apply… R3."""
    o1 = po(db, s, "PO-2026-101", created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    po(db, s, "PO-2026-102", created_at=datetime(2026, 3, 5, 0, 0, 0))
    o3 = po(db, s, "PO-2026-103", created_at=datetime(2026, 3, 1, 8, 0, 0))
    result = hub(db, s.W1, date_to=DAY)
    # Then 1
    assert idset(result) == {o1.id, o3.id}


# [claude] PUO-HF-11
def test_puo_hf_11__same_day_range(db, s):
    """PUO-HF-11 — date_from and date_to on the same day keep exactly that day.
    Rules: _apply… R3, R13."""
    o1 = po(db, s, "PO-2026-101", created_at=datetime(2026, 3, 4, 0, 0, 0))
    o2 = po(db, s, "PO-2026-102", created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    po(db, s, "PO-2026-103", created_at=datetime(2026, 3, 3, 23, 59, 59, 999999))
    po(db, s, "PO-2026-104", created_at=datetime(2026, 3, 5, 0, 0, 0))
    result = hub(db, s.W1, date_from=DAY, date_to=DAY)
    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] PUO-HF-12
def test_puo_hf_12__from_after_to_gives_nothing(db, s):
    """PUO-HF-12 — date_from after date_to gives nothing, with no error.
    Rules: _apply… R3."""
    po(db, s, "PO-2026-101", created_at=datetime(2026, 3, 4, 12, 0, 0))
    po(db, s, "PO-2026-102", created_at=datetime(2026, 3, 5, 12, 0, 0))
    result = hub(db, s.W1, date_from=date(2026, 3, 5), date_to=DAY)
    # Then 1
    assert result == []


# [claude] PUO-HF-13
def test_puo_hf_13__status_ids_one_stage(db, s):
    """PUO-HF-13 — status_ids keeps that stage, with a lower and a higher status id beside it.
    Rules: _apply… R4."""
    po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **stage(s.SP1))
    po(db, s, "PO-2026-103", **stage(s.SR1))
    result = hub(db, s.W1, status_ids=[s.SP1.id])
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-14
def test_puo_hf_14__two_status_ids(db, s):
    """PUO-HF-14 — two status ids keep both stages.
    Rules: _apply… R4."""
    o1 = po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **stage(s.SP1))
    o3 = po(db, s, "PO-2026-103", **stage(s.SR1))
    result = hub(db, s.W1, status_ids=[s.SD1.id, s.SR1.id])
    # Then 1
    assert idset(result) == {o1.id, o3.id}


# [claude] PUO-HF-15
def test_puo_hf_15__empty_status_ids_no_filter(db, s):
    """PUO-HF-15 — an empty status_ids list is no filter.
    Rules: _apply… R4."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **stage(s.SP1))
    o3 = po(db, s, "PO-2026-103", **stage(s.SR1))
    result = hub(db, s.W1, status_ids=[])
    # Then 1
    assert idset(result) == {o1.id, o2.id, o3.id}


# [claude] PUO-HF-16
def test_puo_hf_16__destination_type(db, s):
    """PUO-HF-16 — destination_type keeps that type only.
    Rules: _apply… R5."""
    po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **to_machine(s.M1))
    po(db, s, "PO-2026-103", **to_component(s.C1))
    result = hub(db, s.W1, destination_type="machine")
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-17
def test_puo_hf_17__destination_type_case_sensitive(db, s):
    """PUO-HF-17 — destination_type is compared case-sensitively.
    Rules: _apply… R5."""
    po(db, s, "PO-2026-101", **to_machine(s.M1))
    result = hub(db, s.W1, destination_type="Machine")
    # Then 1
    assert result == []


# [claude] PUO-HF-18
def test_puo_hf_18__part_of_destination_type(db, s):
    """PUO-HF-18 — part of a destination type does not match.
    Rules: _apply… R5."""
    po(db, s, "PO-2026-101", **to_machine(s.M1))
    result = hub(db, s.W1, destination_type="mach")
    # Then 1
    assert result == []


# [claude] PUO-HF-19
def test_puo_hf_19__empty_destination_type(db, s):
    """PUO-HF-19 — an empty destination_type is no filter.
    Rules: _apply… R5."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **to_machine(s.M1))
    result = hub(db, s.W1, destination_type="")
    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] PUO-HF-20
def test_puo_hf_20__factory_storage(db, s):
    """PUO-HF-20 — factory filter keeps storage POs of that factory, not of a lower or higher factory.
    Rules: _apply… R6."""
    po(db, s, "PO-2026-101", **to_storage(s.FA))
    o2 = po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103", **to_storage(s.FZ))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-21
def test_puo_hf_21__factory_machine(db, s):
    """PUO-HF-21 — factory filter keeps POs for a machine of that factory.
    Rules: _apply… R6."""
    po(db, s, "PO-2026-101", **to_machine(s.MA))
    o2 = po(db, s, "PO-2026-102", **to_machine(s.M1))
    po(db, s, "PO-2026-103", **to_machine(s.MZ))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-22
def test_puo_hf_22__factory_component(db, s):
    """PUO-HF-22 — factory filter keeps POs for a component of a project of that factory.
    Rules: _apply… R6."""
    po(db, s, "PO-2026-101", **to_component(s.CA))
    o2 = po(db, s, "PO-2026-102", **to_component(s.C1))
    po(db, s, "PO-2026-103", **to_component(s.CZ))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-23
def test_puo_hf_23__deleted_machine_still_counts(db, s):
    """PUO-HF-23 — a deleted machine still places its PO under the factory.
    Rules: _apply… R6."""
    md = _add(
        db,
        Machine(
            workspace_id=s.W1.id,
            factory_id=s.F1.id,
            name="Press Old",
            **closed_account(s),
        ),
    )
    o1 = po(db, s, "PO-2026-101", **to_machine(md))
    po(db, s, "PO-2026-102", **to_machine(s.MZ))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-24
def test_puo_hf_24__removed_component_no_longer_counts(db, s):
    """PUO-HF-24 — a removed component no longer places its PO under the factory.
    Rules: _apply… R6."""
    cd = _add(
        db, ProjectComponent(workspace_id=s.W1.id, project_id=s.PJ1.id, name="Part Old")
    )
    o1 = po(db, s, "PO-2026-101", **to_component(cd))
    o2 = po(db, s, "PO-2026-102", **to_component(s.C1))
    cd_id = cd.id
    db.delete(cd)
    db.flush()
    o1_id = o1.id
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}
    # Then 2
    row = reread_po(db, o1_id)
    assert row.destination_type == "project"
    assert row.destination_id == cd_id


# [claude] PUO-HF-25
def test_puo_hf_25__machine_id_equal_to_factory_id(db, s):
    """PUO-HF-25 — a machine whose id equals the factory id does not count unless it belongs to it.
    Rules: _apply… R6."""
    fx = _add(
        db,
        Factory(workspace_id=s.W1.id, name="Extra Plant", abbreviation="XP", id=xid(1)),
    )
    mx = _add(
        db, Machine(workspace_id=s.W1.id, factory_id=s.FZ.id, name="Press X", id=xid(1))
    )
    po(db, s, "PO-2026-101", **to_machine(mx))
    o2 = po(db, s, "PO-2026-102", **to_storage(fx))
    result = hub(db, s.W1, factory_id=fx.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-26
def test_puo_hf_26__storage_id_equal_to_machine_id(db, s):
    """PUO-HF-26 — a storage PO whose destination id is a machine of the factory is not kept.
    Rules: _apply… R6."""
    my = _add(
        db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Press Y", id=xid(2))
    )
    po(db, s, "PO-2026-101", destination_type="storage", destination_id=xid(2))
    o2 = po(db, s, "PO-2026-102", **to_machine(my))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-27
def test_puo_hf_27__storage_id_equal_to_component_id(db, s):
    """PUO-HF-27 — a storage PO whose destination id is a component of the factory is not kept.
    Rules: _apply… R6."""
    cx = _add(
        db,
        ProjectComponent(
            workspace_id=s.W1.id, project_id=s.PJ1.id, name="Part X", id=xid(3)
        ),
    )
    po(db, s, "PO-2026-101", destination_type="storage", destination_id=xid(3))
    o2 = po(db, s, "PO-2026-102", **to_component(cx))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-28
def test_puo_hf_28__unknown_destination_type(db, s):
    """PUO-HF-28 — an unknown destination type pointing at the factory id is not kept.
    Rules: _apply… R6."""
    po(db, s, "PO-2026-101", destination_type="warehouse", destination_id=s.F1.id)
    o2 = po(db, s, "PO-2026-102")
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-29
def test_puo_hf_29__factory_without_po(db, s):
    """PUO-HF-29 — a factory with no PO gives nothing.
    Rules: _apply… R6."""
    po(db, s, "PO-2026-101")
    result = hub(db, s.W1, factory_id=s.FZ.id)
    # Then 1
    assert result == []


# [claude] PUO-HF-30
def test_puo_hf_30__invoiced(db, s):
    """PUO-HF-30 — invoiced keeps POs with an invoice.
    Rules: _apply… R7."""
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po(db, s, "PO-2026-102")
    result = hub(db, s.W1, invoice_filter="invoiced")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-31
def test_puo_hf_31__not_invoiced(db, s):
    """PUO-HF-31 — not_invoiced keeps POs without an invoice.
    Rules: _apply… R7."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    o2 = po(db, s, "PO-2026-102")
    result = hub(db, s.W1, invoice_filter="not_invoiced")
    # Then 1
    assert idset(result) == {o2.id}


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("bogus", id="PUO-HF-32"),
        pytest.param("all", id="PUO-HF-33"),
        pytest.param("", id="PUO-HF-34"),
    ],
)
# [claude] PUO-HF-32, HF-33, HF-34
def test_puo_hf_32_33_34__invoice_filter_no_filter(db, s, value):
    """PUO-HF-32 … HF-34 — an unknown, "all" or empty invoice_filter is no filter.
    Rules: _apply… R8."""
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    o2 = po(db, s, "PO-2026-102")
    result = hub(db, s.W1, invoice_filter=value)
    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] PUO-HF-35
def test_puo_hf_35__default_excludes_voided_and_closed(db, s):
    """PUO-HF-35 — by default voided and fully closed POs are left out; Complete unpaid and paid Receiving stay.
    Rules: _apply… R10; _purchase_order_is_fully_closed_clause R1, R2; list_for_hub R1."""
    o1 = po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **closed(s))
    po(db, s, "PO-2026-103", **voided(s))
    o4 = po(db, s, "PO-2026-104", **stage(s.SC1))
    o5 = po(db, s, "PO-2026-105", **stage(s.SR1), paid=True)
    result = hub(db, s.W1)
    # Then 1
    assert idset(result) == {o1.id, o4.id, o5.id}


# [claude] PUO-HF-36
def test_puo_hf_36__exclude_voided_false(db, s):
    """PUO-HF-36 — exclude_voided=False keeps voided POs; fully closed stay out.
    Rules: _apply… R10."""
    o1 = po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **closed(s))
    o3 = po(db, s, "PO-2026-103", **voided(s))
    o4 = po(db, s, "PO-2026-104", **stage(s.SC1))
    result = hub(db, s.W1, exclude_voided=False)
    # Then 1
    assert idset(result) == {o1.id, o3.id, o4.id}


# [claude] PUO-HF-37
def test_puo_hf_37__exclude_complete_false(db, s):
    """PUO-HF-37 — exclude_complete=False keeps fully closed POs; voided stay out.
    Rules: _apply… R10."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **closed(s))
    po(db, s, "PO-2026-103", **voided(s))
    o4 = po(db, s, "PO-2026-104", **stage(s.SC1))
    result = hub(db, s.W1, exclude_complete=False)
    # Then 1
    assert idset(result) == {o1.id, o2.id, o4.id}


# [claude] PUO-HF-38
def test_puo_hf_38__both_switches_off(db, s):
    """PUO-HF-38 — both switches off keep every PO (O4 is legacy data: closed and voided).
    Rules: _apply… R10."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102", **closed(s))
    o3 = po(db, s, "PO-2026-103", **voided(s))
    o4 = po(db, s, "PO-2026-104", **closed(s), **voided(s))
    result = hub(db, s.W1, exclude_complete=False, exclude_voided=False)
    # Then 1
    assert idset(result) == {o1.id, o2.id, o3.id, o4.id}


# [claude] PUO-HF-39
def test_puo_hf_39__search_middle_of_number(db, s):
    """PUO-HF-39 — search finds text in the middle of the PO number.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417")
    po(db, s, "PO-2026-520", account_id=s.AH1.id)
    result = hub(db, s.W1, search="6-41")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-40
def test_puo_hf_40__search_number_ignores_case(db, s):
    """PUO-HF-40 — search on the number ignores case.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417", account_id=s.AH1.id)
    po(db, s, "XO-2026-520", account_id=s.AH1.id)
    result = hub(db, s.W1, search="po-2026")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-41
def test_puo_hf_41__search_middle_of_supplier(db, s):
    """PUO-HF-41 — search finds text in the middle of the supplier name.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417")
    po(db, s, "PO-2026-520", account_id=s.AH1.id)
    result = hub(db, s.W1, search="wind Tra")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-42
def test_puo_hf_42__search_supplier_ignores_case(db, s):
    """PUO-HF-42 — search on the supplier name ignores case.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417")
    po(db, s, "PO-2026-520", account_id=s.AH1.id)
    result = hub(db, s.W1, search="NORTHWIND TRADERS")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-43
def test_puo_hf_43__search_trimmed(db, s):
    """PUO-HF-43 — search text is trimmed before matching.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417", account_id=s.AH1.id)
    po(db, s, "PO-2026-520", account_id=s.AH1.id)
    result = hub(db, s.W1, search="  417  ")
    # Then 1
    assert idset(result) == {o1.id}


@pytest.mark.parametrize(
    "value",
    [pytest.param("   ", id="PUO-HF-44"), pytest.param("", id="PUO-HF-45")],
)
# [claude] PUO-HF-44, HF-45
def test_puo_hf_44_45__blank_search_no_filter(db, s, value):
    """PUO-HF-44, HF-45 — a whitespace-only or empty search is no filter.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417")
    o2 = po(db, s, "PO-2026-520", **NO_SUPPLIER)
    result = hub(db, s.W1, search=value)
    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] PUO-HF-46
def test_puo_hf_46__w0_supplier_name_no_match(db, s):
    """PUO-HF-46 — the earlier workspace's supplier name does not match in W1.
    Rules: _apply… R1, R11; HR-16."""
    po0(db, s, "PO-2026-417")
    po(db, s, "PO-2026-520")
    result = hub(db, s.W1, search="West")
    # Then 1
    assert result == []


# [claude] PUO-HF-47
def test_puo_hf_47__w2_supplier_name_no_match(db, s):
    """PUO-HF-47 — the later workspace's supplier name does not match in W1.
    Rules: _apply… R1, R11; HR-16."""
    po(db, s, "PO-2026-520")
    po2(db, s, "PO-2026-417")
    result = hub(db, s.W1, search="East")
    # Then 1
    assert result == []


# [claude] PUO-HF-48
def test_puo_hf_48__no_supplier_found_by_number(db, s):
    """PUO-HF-48 — a PO with no supplier is found by its number.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-417", **NO_SUPPLIER)
    po(db, s, "PO-2026-520", **NO_SUPPLIER)
    result = hub(db, s.W1, search="417")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-49
def test_puo_hf_49__name_search_skips_no_supplier(db, s):
    """PUO-HF-49 — a name search skips a PO with no supplier, with no error.
    Rules: _apply… R11."""
    po(db, s, "PO-2026-417", **NO_SUPPLIER)
    o2 = po(db, s, "PO-2026-520")
    result = hub(db, s.W1, search="Northwind")
    # Then 1
    assert idset(result) == {o2.id}


# [claude] PUO-HF-50
def test_puo_hf_50__underscore_search_finds_it(db, s):
    """PUO-HF-50 — a search with `_` finds the PO whose number has it.
    Rules: _apply… R11."""
    o1 = po(db, s, "PO-2026-5_1")
    result = hub(db, s.W1, search="5_1")
    # Then 1
    assert o1.id in idset(result)


# [claude] PUO-HF-51
@pytest.mark.xfail(strict=True, reason=B2633)
def test_puo_hf_51__underscore_literal(db, s):
    """PUO-HF-51 — `_` in the search matches only a literal underscore.
    Rules: _apply… R11 [BUG-2633]."""
    o1 = po(db, s, "PO-2026-5_1")
    po(db, s, "PO-2026-501")
    result = hub(db, s.W1, search="5_1")
    # Then 1
    assert o1.id in idset(result)
    # Then 2
    assert idset(result) == {o1.id}


# [claude] PUO-HF-52
@pytest.mark.xfail(strict=True, reason=B2633)
def test_puo_hf_52__percent_literal(db, s):
    """PUO-HF-52 — `%` in the search matches only a literal percent sign.
    Rules: _apply… R11 [BUG-2633]."""
    o1 = po(db, s, "PO-2026-7%0")
    po(db, s, "PO-2026-700")
    result = hub(db, s.W1, search="7%0")
    # Then 1
    assert o1.id in idset(result)
    # Then 2
    assert idset(result) == {o1.id}


# [claude] PUO-HF-53
@pytest.mark.xfail(strict=True, reason=B2633)
def test_puo_hf_53__backslash_literal(db, s):
    """PUO-HF-53 — a backslash in the search matches a literal backslash.
    Rules: _apply… R11 [BUG-2633]."""
    o1 = po(db, s, "PO-2026-8\\9")
    po(db, s, "PO-2026-89")
    result = hub(db, s.W1, search="8\\9")
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {o1.id}


# [claude] PUO-HF-54
@pytest.mark.xfail(strict=True, reason=B2633)
def test_puo_hf_54__underscore_alone(db, s):
    """PUO-HF-54 — a search of `_` alone matches no PO without an underscore.
    Rules: _apply… R11 [BUG-2633]."""
    po(db, s, "PO-2026-001")
    po(db, s, "PO-2026-002", **NO_SUPPLIER)
    result = hub(db, s.W1, search="_")
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] PUO-HF-55
@pytest.mark.xfail(strict=True, reason=B2633)
def test_puo_hf_55__percent_alone(db, s):
    """PUO-HF-55 — a search of `%` alone matches no PO without a percent sign.
    Rules: _apply… R11 [BUG-2633]."""
    po(db, s, "PO-2026-001")
    po(db, s, "PO-2026-002", **NO_SUPPLIER)
    result = hub(db, s.W1, search="%")
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] PUO-HF-56
@pytest.mark.xfail(strict=True, reason=B2634)
def test_puo_hf_56__deleted_supplier_name_no_match(db, s):
    """PUO-HF-56 — a soft-deleted supplier's name does not match.
    Rules: _apply… R12 [BUG-2634]."""
    da = _add(
        db, Account(workspace_id=s.W1.id, name="Delta Freight", **closed_account(s))
    )
    po(db, s, "PO-2026-417", account_id=da.id)
    po(db, s, "PO-2026-520")
    result = hub(db, s.W1, search="Delta")
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [claude] PUO-HF-57
def test_puo_hf_57__deleted_supplier_po_found_by_number(db, s):
    """PUO-HF-57 — a PO of a soft-deleted supplier is still found by its number.
    Rules: _apply… R12, R11."""
    da = _add(
        db, Account(workspace_id=s.W1.id, name="Delta Freight", **closed_account(s))
    )
    o1 = po(db, s, "PO-2026-417", account_id=da.id)
    po(db, s, "PO-2026-520")
    result = hub(db, s.W1, search="417")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-58
def test_puo_hf_58__filters_and(db, s):
    """PUO-HF-58 — filters combine with AND.
    Rules: _apply… R13."""
    o1 = po(db, s, "PO-2026-101", **stage(s.SP1))
    po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103", **stage(s.SP1), account_id=s.AL1.id)
    result = hub(db, s.W1, account_id=s.A1.id, status_ids=[s.SP1.id])
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-HF-59
def test_puo_hf_59__joins_no_duplicate(db, s):
    """PUO-HF-59 — supplier, invoice and status joins together add no duplicate row.
    Rules: _apply… R13."""
    o1 = po(db, s, "PO-2026-417", **stage(s.SP1), invoice_id=s.V1.id)
    result = hub(
        db, s.W1, search="Northwind", invoice_filter="invoiced", exclude_complete=True
    )
    # Then 1
    assert ids(result) == [o1.id]


# [claude] PUO-HF-60
def test_puo_hf_60__unknown_keyword(db, s):
    """PUO-HF-60 — an unknown filter keyword raises TypeError.
    Rules: _apply… R14."""
    po(db, s, "PO-2026-101")
    before = totals(db)
    # Then 1
    with pytest.raises(TypeError):
        hub(db, s.W1, supplier_id=s.A1.id)
    # Then 2
    assert totals(db) == before


# [claude] PUO-HF-61
def test_puo_hf_61__deleted_project_still_counts(db, s):
    """PUO-HF-61 — a soft-deleted project still places its components' POs under its factory.
    Rules: _apply… R6."""
    pjd = _add(
        db,
        Project(
            workspace_id=s.W1.id,
            factory_id=s.F1.id,
            name="Project Old",
            description="Main",
            **deleted_project(s),
        ),
    )
    cpd = _add(
        db, ProjectComponent(workspace_id=s.W1.id, project_id=pjd.id, name="Part Old")
    )
    o1 = po(db, s, "PO-2026-101", **to_component(cpd))
    po(db, s, "PO-2026-102", **to_component(s.CZ))
    result = hub(db, s.W1, factory_id=s.F1.id)
    # Then 1
    assert idset(result) == {o1.id}


# =========================================================================== #
# PurchaseOrderDAO.list_for_hub
# =========================================================================== #


# [claude] PUO-LH-01
def test_puo_lh_01__newest_created_first(db, s):
    """PUO-LH-01 — newest created_at first, though ids, numbers and suppliers run otherwise.
    Rules: list_for_hub R2."""
    o1 = po(db, s, "PO-2026-004", created_at=T2, account_id=s.AH1.id)
    o2 = po(db, s, "PO-2026-001", created_at=T4)
    o3 = po(db, s, "PO-2026-003", created_at=T1, account_id=s.AL1.id)
    o4 = po(db, s, "PO-2026-002", created_at=T3)
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [o2.id, o4.id, o1.id, o3.id]


# [claude] PUO-LH-02
def test_puo_lh_02__tie_higher_id_first_after_update(db, s):
    """PUO-LH-02 — on a created_at tie the higher id comes first, also after the lowest id was updated.
    Rules: list_for_hub R2."""
    a = po(db, s, "PO-2026-003", created_at=T2, account_id=s.AH1.id)
    b = po(db, s, "PO-2026-001", created_at=T2)
    c = po(db, s, "PO-2026-002", created_at=T2, account_id=s.AL1.id)
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_p(db, a)
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [c_id, b_id, a_id]


# [claude] PUO-LH-03
def test_puo_lh_03__tie_high_explicit_id_first(db, s):
    """PUO-LH-03 — on a created_at tie a row with a high explicit id comes first.
    Rules: list_for_hub R2."""
    eb = po(db, s, "PO-2026-001", created_at=T2)
    eh = po(db, s, "PO-2026-002", created_at=T2, id="HIGH")
    ea = po(db, s, "PO-2026-003", created_at=T2)
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [eh.id, ea.id, eb.id]


# [claude] PUO-LH-04
def test_puo_lh_04__orders_by_created_at_then_id_desc(db, s):
    """PUO-LH-04 — the query orders by created_at, then id, both descending.
    Rules: list_for_hub R2."""
    o1 = po(db, s, "PO-2026-001")
    with Recorder(db) as rec:
        result = dao.list_for_hub(db, workspace_id=s.W1.id)
    op = order_part(rec.sql)
    # Then 1
    assert ids(result) == [o1.id]
    # Then 2
    assert "created_at" in op
    # Then 3
    assert "purchase_orders.id" in op
    # Then 4
    assert op.index("created_at") < op.index("purchase_orders.id")
    # Then 5
    assert op.upper().count("DESC") == 2


# [claude] PUO-LH-05
def test_puo_lh_05__skip_and_limit(db, s):
    """PUO-LH-05 — skip and limit select the middle of the list.
    Rules: list_for_hub R3."""
    r = pos(db, s, 7)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=2, limit=3)
    # Then 1
    assert ids(result) == [r[4].id, r[3].id, r[2].id]


# [claude] PUO-LH-06
def test_puo_lh_06__default_limit_50(db, s):
    """PUO-LH-06 — the default limit is 50.
    Rules: list_for_hub R3."""
    r = pos(db, s, 51)
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 50
    # Then 2
    assert r[0].id not in idset(result)


# [claude] PUO-LH-07
def test_puo_lh_07__default_skip_0(db, s):
    """PUO-LH-07 — the default skip is 0.
    Rules: list_for_hub R3."""
    r = pos(db, s, 3)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, limit=2)
    # Then 1
    assert ids(result) == [r[2].id, r[1].id]


# [claude] PUO-LH-08
def test_puo_lh_08__limit_1000_all_rows(db, s):
    """PUO-LH-08 — limit=1000 returns all 51 rows.
    Rules: list_for_hub R3."""
    pos(db, s, 51)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, limit=1000)
    # Then 1
    assert len(result) == 51


# [claude] PUO-LH-09
def test_puo_lh_09__filters_before_paging(db, s):
    """PUO-LH-09 — filters apply before paging: a newer hidden PO does not use a page slot.
    Rules: list_for_hub R3; HR-5."""
    po(db, s, "PO-2026-001", created_at=T1)
    po(db, s, "PO-2026-002", created_at=T5, **voided(s))
    po(db, s, "PO-2026-003", created_at=T4)
    o2 = po(db, s, "PO-2026-004", created_at=T3)
    o3 = po(db, s, "PO-2026-005", created_at=T2)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert ids(result) == [o2.id, o3.id]


# [claude] PUO-LH-10
def test_puo_lh_10__page_full_with_hidden_pos(db, s):
    """PUO-LH-10 — a page is full when enough POs match, though hidden POs exist.
    Rules: list_for_hub R3; HR-5."""
    r = pos(db, s, 5)
    po(db, s, "PO-2026-901", created_at=T5, **voided(s))
    po(db, s, "PO-2026-902", created_at=T4, **closed(s))
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=0, limit=5)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert idset(result) == {r[0].id, r[1].id, r[2].id, r[3].id, r[4].id}


# [claude] PUO-LH-11
def test_puo_lh_11__writes_nothing_keeps_pending(db, s):
    """PUO-LH-11 — writes nothing, keeps the caller's pending row and edit, takes no lock.
    Rules: list_for_hub Side effects."""
    o1 = po(db, s, "PO-2026-001")
    p = edit_pending(db, s, o1)
    before = totals(db)
    with Recorder(db) as rec:
        result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [o1.id]
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)
    # Then 8
    assert totals(db) == before


# [claude] PUO-LH-12
def test_puo_lh_12__workspace_without_po(db, s):
    """PUO-LH-12 — a workspace with no PO gives an empty list.
    Rules: list_for_hub R1."""
    po0(db, s, "PO-2026-001")
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PUO-LH-13
def test_puo_lh_13__status_loaded(db, s):
    """PUO-LH-13 — the current status comes loaded with each PO.
    Rules: list_for_hub R1 (Returns: current status loaded)."""
    po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **stage(s.SP1))
    db.expunge_all()
    result = dao.list_for_hub(db, workspace_id=s.W1.id, limit=1000)
    # Then 1
    assert all("current_status" not in sa_inspect(r).unloaded for r in result)
    # Then 2
    assert {r.current_status.name for r in result} == {"Draft", "Planning"}


# =========================================================================== #
# PurchaseOrderDAO.count_for_hub
# =========================================================================== #


# [claude] PUO-CH-01
def test_puo_ch_01__counts_matching_as_int(db, s):
    """PUO-CH-01 — counts the POs matching the filters, as an int.
    Rules: count_for_hub R1."""
    po(db, s, "PO-2026-101", **stage(s.SP1))
    po(db, s, "PO-2026-102", **stage(s.SP1))
    po(db, s, "PO-2026-103")
    result = dao.count_for_hub(db, workspace_id=s.W1.id, status_ids=[s.SP1.id])
    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 2


# [claude] PUO-CH-02
def test_puo_ch_02__no_match_zero(db, s):
    """PUO-CH-02 — no match gives 0.
    Rules: count_for_hub R1."""
    po(db, s, "PO-2026-101")
    result = dao.count_for_hub(db, workspace_id=s.W1.id, account_id=0)
    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 0


# [claude] PUO-CH-03
def test_puo_ch_03__default_excludes(db, s):
    """PUO-CH-03 — by default voided and fully closed POs are not counted.
    Rules: count_for_hub R1; _apply… R10."""
    po(db, s, "PO-2026-101")
    po(db, s, "PO-2026-102", **closed(s))
    po(db, s, "PO-2026-103", **voided(s))
    po(db, s, "PO-2026-104", **stage(s.SC1))
    result = dao.count_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == 2


# [claude] PUO-CH-04
def test_puo_ch_04__not_capped(db, s):
    """PUO-CH-04 — the count is not capped by the list's page size.
    Rules: count_for_hub R1."""
    pos(db, s, 60)
    result = dao.count_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == 60


# [claude] PUO-CH-05
def test_puo_ch_05__only_w1(db, s):
    """PUO-CH-05 — only W1's POs are counted, with more POs in W0 and W2.
    Rules: count_for_hub R1; _apply… R1."""
    po0(db, s, "PO-2026-001")
    po0(db, s, "PO-2026-002")
    po(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-002")
    po2(db, s, "PO-2026-003")
    result = dao.count_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == 1


# [claude] PUO-CH-06
def test_puo_ch_06__asked_for_w2(db, s):
    """PUO-CH-06 — asked for W2, W2's POs are counted.
    Rules: count_for_hub R1; _apply… R1."""
    po0(db, s, "PO-2026-001")
    po(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-001")
    po2(db, s, "PO-2026-002")
    po2(db, s, "PO-2026-003")
    result = dao.count_for_hub(db, workspace_id=s.W2.id)
    # Then 1
    assert result == 3


# [claude] PUO-CH-07
def test_puo_ch_07__joins_count_once(db, s):
    """PUO-CH-07 — the joins of search, invoice filter and stage count each PO once.
    Rules: count_for_hub R1; _apply… R13."""
    po(db, s, "PO-2026-417", **stage(s.SP1), invoice_id=s.V1.id)
    po(db, s, "PO-2026-418", **stage(s.SR1), invoice_id=s.V2.id)
    result = dao.count_for_hub(
        db,
        workspace_id=s.W1.id,
        search="Northwind",
        invoice_filter="invoiced",
        exclude_complete=True,
    )
    # Then 1
    assert result == 2


# [claude] PUO-CH-08
def test_puo_ch_08__writes_nothing(db, s):
    """PUO-CH-08 — writes nothing and takes no lock.
    Rules: count_for_hub Side effects."""
    o1 = po(db, s, "PO-2026-001")
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = dao.count_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == 1
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# =========================================================================== #
# PurchaseOrderDAO.list_recent_for_hub
# =========================================================================== #


# [claude] PUO-RH-01
@pytest.mark.xfail(strict=True, reason=B2635)
def test_puo_rh_01__edited_latest_activity_first(db, s):
    """PUO-RH-01 — an edited PO with the latest activity comes before never-edited newer ones.
    Rules: list_recent_for_hub R1 [BUG-2635]."""
    e = po(db, s, "PO-2026-001", created_at=T1, **edited(s, T5))
    n1 = po(db, s, "PO-2026-002", created_at=T4)
    n2 = po(db, s, "PO-2026-003", created_at=T2)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [e.id, n1.id, n2.id]


# [claude] PUO-RH-02
def test_puo_rh_02__never_edited_newest_first(db, s):
    """PUO-RH-02 — never-edited POs come newest created_at first.
    Rules: list_recent_for_hub R1."""
    n1 = po(db, s, "PO-2026-003", created_at=T2)
    n2 = po(db, s, "PO-2026-001", created_at=T4)
    n3 = po(db, s, "PO-2026-002", created_at=T1)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [n2.id, n1.id, n3.id]


# [claude] PUO-RH-03
def test_puo_rh_03__edited_latest_edit_first(db, s):
    """PUO-RH-03 — edited POs come latest edit first, whatever their created_at.
    Rules: list_recent_for_hub R1."""
    e1 = po(db, s, "PO-2026-001", created_at=T1, **edited(s, T3))
    e2 = po(
        db, s, "PO-2026-002", created_at=T4, **edited(s, datetime(2026, 3, 4, 12, 30))
    )
    e3 = po(db, s, "PO-2026-003", created_at=T2, **edited(s, T5))
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PUO-RH-04
@pytest.mark.xfail(strict=False, reason=B2635)
def test_puo_rh_04__activity_tie_higher_id_first(db, s):
    """PUO-RH-04 — on an activity tie the higher id comes first (seqscan + bump, non-strict).
    Rules: list_recent_for_hub R1 [BUG-2635]."""
    a = po(db, s, "PO-2026-003", created_at=T2)
    b = po(db, s, "PO-2026-001", created_at=T2)
    c = po(db, s, "PO-2026-002", created_at=T2)
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_p(db, a)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c_id, b_id, a_id]


# [claude] PUO-RH-05
@pytest.mark.xfail(strict=True, reason=B2635)
def test_puo_rh_05__orders_by_coalesce_then_id(db, s):
    """PUO-RH-05 — the query orders by coalesce(updated_at, created_at), then id.
    Rules: list_recent_for_hub R1 [BUG-2635]."""
    o1 = po(db, s, "PO-2026-001")
    with Recorder(db) as rec:
        result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    op = order_part(rec.sql)
    # Then 1
    assert ids(result) == [o1.id]
    # Then 2
    assert "coalesce" in op.lower()
    # Then 3
    assert "purchase_orders.id" in op


# [claude] PUO-RH-06
def test_puo_rh_06__default_limit_10(db, s):
    """PUO-RH-06 — the default limit is 10.
    Rules: list_recent_for_hub R1."""
    r = pos(db, s, 11)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 10
    # Then 2
    assert r[0].id not in idset(result)


# [claude] PUO-RH-07
def test_puo_rh_07__limit_2(db, s):
    """PUO-RH-07 — limit=2 gives the two latest.
    Rules: list_recent_for_hub R1."""
    r = pos(db, s, 3)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, limit=2)
    # Then 1
    assert ids(result) == [r[2].id, r[1].id]


# [claude] PUO-RH-08
def test_puo_rh_08__limit_1000(db, s):
    """PUO-RH-08 — limit=1000 returns all 11 rows.
    Rules: list_recent_for_hub R1."""
    pos(db, s, 11)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, limit=1000)
    # Then 1
    assert len(result) == 11


# [claude] PUO-RH-09
def test_puo_rh_09__hub_filters_apply(db, s):
    """PUO-RH-09 — the hub filters and defaults apply.
    Rules: list_recent_for_hub R2."""
    po0(db, s, "PO-2026-001", created_at=T5)
    o1 = po(db, s, "PO-2026-001", created_at=T1)
    po(db, s, "PO-2026-002", created_at=T4, **voided(s))
    po(db, s, "PO-2026-003", created_at=T4, **closed(s))
    po(db, s, "PO-2026-004", created_at=T2, account_id=s.AL1.id)
    po2(db, s, "PO-2026-001", created_at=T5)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, account_id=s.A1.id)
    # Then 1
    assert ids(result) == [o1.id]


# [claude] PUO-RH-10
def test_puo_rh_10__writes_nothing(db, s):
    """PUO-RH-10 — writes nothing and takes no lock.
    Rules: list_recent_for_hub Side effects."""
    o1 = po(db, s, "PO-2026-001")
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = dao.list_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [o1.id]
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# =========================================================================== #
# PurchaseOrderDAO.get_pending_highlights_for_hub
# =========================================================================== #


def highlights(db, ws, **filters):
    return dao.get_pending_highlights_for_hub(db, workspace_id=ws.id, **filters)


# [claude] PUO-PH-01
def test_puo_ph_01__planning_counted_and_listed(db, s):
    """PUO-PH-01 — Planning POs are counted and listed with their fields; Draft and Receiving are not.
    Rules: get_pending_highlights_for_hub R2, R6."""
    p1 = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T2, invoice_id=s.V1.id)
    po(db, s, "PO-2026-002", created_at=T1)
    po(db, s, "PO-2026-003", **stage(s.SR1))
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 1
    # Then 2
    assert result["pending_planning"] == [
        {
            "id": p1.id,
            "order_number": "PO-2026-001",
            "status_name": "Planning",
            "created_at": T2,
        }
    ]


# [claude] PUO-PH-02
def test_puo_ph_02__three_listed_four_counted(db, s):
    """PUO-PH-02 — at most 3 Planning POs are listed, all 4 are counted.
    Rules: get_pending_highlights_for_hub R2."""
    p1 = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T1)
    p2 = po(db, s, "PO-2026-002", **stage(s.SP1), created_at=T2)
    p3 = po(db, s, "PO-2026-003", **stage(s.SP1), created_at=T3)
    p4 = po(db, s, "PO-2026-004", **stage(s.SP1), created_at=T4)
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 4
    # Then 2
    assert len(result["pending_planning"]) == 3
    # Then 3
    assert set(eids(result["pending_planning"])) <= {p1.id, p2.id, p3.id, p4.id}


# [claude] PUO-PH-03
@pytest.mark.xfail(strict=True, reason=B2635)
def test_puo_ph_03__planning_latest_activity_first(db, s):
    """PUO-PH-03 — Planning samples come latest activity first.
    Rules: get_pending_highlights_for_hub R2 [BUG-2635]."""
    e = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T1, **edited(s, T5))
    n1 = po(db, s, "PO-2026-002", **stage(s.SP1), created_at=T4)
    n2 = po(db, s, "PO-2026-003", **stage(s.SP1), created_at=T2)
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 3
    # Then 2
    assert eids(result["pending_planning"]) == [e.id, n1.id, n2.id]


# [claude] PUO-PH-04
@pytest.mark.xfail(strict=False, reason=B2635)
def test_puo_ph_04__planning_tie_higher_id_first(db, s):
    """PUO-PH-04 — Planning samples tied on activity come higher id first (seqscan + bump, non-strict).
    Rules: get_pending_highlights_for_hub R2 [BUG-2635]."""
    a = po(db, s, "PO-2026-003", **stage(s.SP1), created_at=T2)
    b = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T2)
    c = po(db, s, "PO-2026-002", **stage(s.SP1), created_at=T2)
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_p(db, a)
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 3
    # Then 2
    assert eids(result["pending_planning"]) == [c_id, b_id, a_id]


# [claude] PUO-PH-05
@pytest.mark.xfail(strict=True, reason=B2635)
def test_puo_ph_05__missing_invoice_latest_activity_first(db, s):
    """PUO-PH-05 — missing-invoice samples come latest activity first.
    Rules: get_pending_highlights_for_hub R3 [BUG-2635]."""
    e = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T1, **edited(s, T5))
    n1 = po(db, s, "PO-2026-002", **stage(s.SP1), created_at=T4)
    n2 = po(db, s, "PO-2026-003", **stage(s.SP1), created_at=T2)
    result = highlights(db, s.W1)
    # Then 1
    assert result["missing_invoice_count"] == 3
    # Then 2
    assert eids(result["missing_invoice"]) == [e.id, n1.id, n2.id]


# [claude] PUO-PH-06
def test_puo_ph_06__missing_invoice_definition(db, s):
    """PUO-PH-06 — "missing invoice" is a Planning PO with a supplier and no invoice.
    Rules: get_pending_highlights_for_hub R3."""
    m1 = po(db, s, "PO-2026-001", **stage(s.SP1))
    po(db, s, "PO-2026-002", **stage(s.SP1), invoice_id=s.V1.id)
    po(db, s, "PO-2026-003", **stage(s.SP1), **NO_SUPPLIER)
    po(db, s, "PO-2026-004")
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 3
    # Then 2
    assert result["missing_invoice_count"] == 1
    # Then 3
    assert eids(result["missing_invoice"]) == [m1.id]
    # Then 4
    assert result["missing_invoice"][0] == {
        "id": m1.id,
        "order_number": "PO-2026-001",
        "status_name": "Planning",
        "created_at": T3,
    }


# [claude] PUO-PH-07
def test_puo_ph_07__missing_three_listed_four_counted(db, s):
    """PUO-PH-07 — at most 3 missing-invoice POs are listed, all 4 are counted.
    Rules: get_pending_highlights_for_hub R3."""
    m1 = po(db, s, "PO-2026-001", **stage(s.SP1), created_at=T1)
    m2 = po(db, s, "PO-2026-002", **stage(s.SP1), created_at=T2)
    m3 = po(db, s, "PO-2026-003", **stage(s.SP1), created_at=T3)
    m4 = po(db, s, "PO-2026-004", **stage(s.SP1), created_at=T4)
    result = highlights(db, s.W1)
    # Then 1
    assert result["missing_invoice_count"] == 4
    # Then 2
    assert len(result["missing_invoice"]) == 3
    # Then 3
    assert set(eids(result["missing_invoice"])) <= {m1.id, m2.id, m3.id, m4.id}


# [claude] PUO-PH-08
def test_puo_ph_08__oldest_five_drafts(db, s):
    """PUO-PH-08 — oldest drafts: the 5 oldest Draft POs, oldest first.
    Rules: get_pending_highlights_for_hub R4, R6."""
    d3 = po(db, s, "PO-2026-001", created_at=T3)
    d1 = po(db, s, "PO-2026-002", created_at=T1)
    po(db, s, "PO-2026-003", created_at=T5)
    d2 = po(db, s, "PO-2026-004", created_at=T2)
    d5 = po(db, s, "PO-2026-005", created_at=datetime(2026, 3, 4, 12, 30))
    d4 = po(db, s, "PO-2026-006", created_at=T4)
    po(db, s, "PO-2026-007", **stage(s.SP1), created_at=T0)
    result = highlights(db, s.W1)
    # Then 1
    assert eids(result["oldest_drafts"]) == [d1.id, d2.id, d3.id, d4.id, d5.id]
    # Then 2
    assert result["oldest_drafts"][0] == {
        "id": d1.id,
        "order_number": "PO-2026-002",
        "status_name": "Draft",
        "created_at": T1,
    }


# [claude] PUO-PH-09
def test_puo_ph_09__four_drafts_all_listed(db, s):
    """PUO-PH-09 — 4 Draft POs are all listed.
    Rules: get_pending_highlights_for_hub R4."""
    d1 = po(db, s, "PO-2026-001", created_at=T1)
    d2 = po(db, s, "PO-2026-002", created_at=T2)
    d3 = po(db, s, "PO-2026-003", created_at=T3)
    d4 = po(db, s, "PO-2026-004", created_at=T4)
    result = highlights(db, s.W1)
    # Then 1
    assert eids(result["oldest_drafts"]) == [d1.id, d2.id, d3.id, d4.id]


# [claude] PUO-PH-10
@pytest.mark.xfail(strict=False, reason=B2636)
def test_puo_ph_10__drafts_tie_lower_id_first(db, s):
    """PUO-PH-10 — oldest drafts tied on created_at come lower id first, after the lowest id was updated.
    Rules: get_pending_highlights_for_hub R5 [BUG-2636]."""
    a = po(db, s, "PO-2026-003", created_at=T2, account_id=s.AH1.id)
    b = po(db, s, "PO-2026-001", created_at=T2)
    c = po(db, s, "PO-2026-002", created_at=T2, account_id=s.AL1.id)
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_p(db, a)
    result = highlights(db, s.W1)
    # Then 1
    assert len(result["oldest_drafts"]) == 3
    # Then 2
    assert eids(result["oldest_drafts"]) == [a_id, b_id, c_id]


# [claude] PUO-PH-11
@pytest.mark.xfail(strict=False, reason=B2636)
def test_puo_ph_11__drafts_tie_high_id_last(db, s):
    """PUO-PH-11 — oldest drafts tied on created_at: a high explicit id comes last.
    Rules: get_pending_highlights_for_hub R5 [BUG-2636]."""
    eb = po(db, s, "PO-2026-001", created_at=T2)
    eh = po(db, s, "PO-2026-002", created_at=T2, id="HIGH")
    ea = po(db, s, "PO-2026-003", created_at=T2)
    result = highlights(db, s.W1)
    # Then 1
    assert len(result["oldest_drafts"]) == 3
    # Then 2
    assert eids(result["oldest_drafts"]) == [eb.id, ea.id, eh.id]


# [claude] PUO-PH-12
@pytest.mark.xfail(strict=True, reason=B2636)
def test_puo_ph_12__drafts_query_orders_created_at_then_id_asc(db, s):
    """PUO-PH-12 — the oldest-drafts query orders by created_at, then id, both ascending.
    Rules: get_pending_highlights_for_hub R4, R5 [BUG-2636]."""
    d1 = po(db, s, "PO-2026-001", created_at=T1)
    with Recorder(db) as rec:
        result = highlights(db, s.W1)
    [draft_sql] = [st for st in rec.selects_with_param("Draft") if "LIMIT" in st]
    op = order_part(draft_sql)
    # Then 1
    assert eids(result["oldest_drafts"]) == [d1.id]
    # Then 2
    assert "created_at" in op
    # Then 3
    assert "purchase_orders.id" in op
    assert op.index("created_at") < op.index("purchase_orders.id")
    assert "DESC" not in op.upper()


# [claude] PUO-PH-13
def test_puo_ph_13__no_match_zero_and_empty(db, s):
    """PUO-PH-13 — no matching PO gives zero counts and empty lists.
    Rules: get_pending_highlights_for_hub R7."""
    po0(db, s, "PO-2026-001", current_status_id=s.SP0.id)
    result = highlights(db, s.W1)
    # Then 1
    assert result == {
        "pending_planning_count": 0,
        "pending_planning": [],
        "missing_invoice_count": 0,
        "missing_invoice": [],
        "oldest_drafts": [],
    }


# [claude] PUO-PH-14
def test_puo_ph_14__other_workspaces_and_voided_out(db, s):
    """PUO-PH-14 — W0's and W2's POs and voided POs are left out by default.
    Rules: get_pending_highlights_for_hub R1."""
    po0(db, s, "PO-2026-001", current_status_id=s.SP0.id)
    po0(db, s, "PO-2026-002")
    p1 = po(db, s, "PO-2026-001", **stage(s.SP1))
    po(db, s, "PO-2026-002", **stage(s.SP1), **voided(s))
    po(db, s, "PO-2026-003", **voided(s))
    po2(db, s, "PO-2026-001", current_status_id=s.SP2.id)
    po2(db, s, "PO-2026-002")
    result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 1
    # Then 2
    assert eids(result["pending_planning"]) == [p1.id]
    # Then 3
    assert result["missing_invoice_count"] == 1
    # Then 4
    assert result["oldest_drafts"] == []


# [claude] PUO-PH-15
def test_puo_ph_15__account_filter_every_part(db, s):
    """PUO-PH-15 — the account filter narrows every part.
    Rules: get_pending_highlights_for_hub R1."""
    p1 = po(db, s, "PO-2026-001", **stage(s.SP1))
    po(db, s, "PO-2026-002", **stage(s.SP1), account_id=s.AL1.id)
    po(db, s, "PO-2026-003", account_id=s.AH1.id)
    result = highlights(db, s.W1, account_id=s.A1.id)
    # Then 1
    assert result["pending_planning_count"] == 1
    # Then 2
    assert result["missing_invoice_count"] == 1
    # Then 3
    assert eids(result["missing_invoice"]) == [p1.id]
    # Then 4
    assert result["oldest_drafts"] == []


# [claude] PUO-PH-16
def test_puo_ph_16__voided_shown_with_status_join(db, s):
    """PUO-PH-16 — exclude_voided=False counts a voided Planning PO; exclude_complete=True works with the status join.
    Rules: get_pending_highlights_for_hub R1."""
    p1 = po(db, s, "PO-2026-001", **stage(s.SP1))
    pv = po(db, s, "PO-2026-002", **stage(s.SP1), **voided(s))
    result = highlights(db, s.W1, exclude_voided=False, exclude_complete=True)
    # Then 1
    assert result["pending_planning_count"] == 2
    # Then 2
    assert set(eids(result["pending_planning"])) == {p1.id, pv.id}


# [claude] PUO-PH-17
def test_puo_ph_17__writes_nothing(db, s):
    """PUO-PH-17 — writes nothing and takes no lock.
    Rules: get_pending_highlights_for_hub Side effects."""
    o1 = po(db, s, "PO-2026-001", **stage(s.SP1))
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = highlights(db, s.W1)
    # Then 1
    assert result["pending_planning_count"] == 1
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# =========================================================================== #
# PurchaseOrderDAO.aggregate_hub_stats
# =========================================================================== #


def stats(db, ws, **filters):
    return dao.aggregate_hub_stats(db, workspace_id=ws.id, **filters)


# [claude] PUO-AS-01
def test_puo_as_01__counts_and_exact_total(db, s):
    """PUO-AS-01 — total count, exact total value and not-invoiced count.
    Rules: aggregate_hub_stats R1, R4, R6."""
    po(db, s, "PO-2026-001", total_amount=Decimal("0.10"), invoice_id=s.V1.id)
    po(db, s, "PO-2026-002", total_amount=Decimal("0.20"))
    po(db, s, "PO-2026-003", total_amount=Decimal("0.30"))
    result = stats(db, s.W1)
    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert len(result) == 5
    # Then 3
    assert result[0] == 3
    # Then 4
    assert result[1] == Decimal("0.60")
    # Then 5
    assert isinstance(result[1], Decimal)
    # Then 6
    assert result[4] == 2


# [claude] PUO-AS-02
def test_puo_as_02__no_match_zeros(db, s):
    """PUO-AS-02 — no matching PO gives zeros.
    Rules: aggregate_hub_stats R5."""
    po0(db, s, "PO-2026-001", total_amount=Decimal("50.00"))
    result = stats(db, s.W1)
    # Then 1
    assert result == (0, Decimal("0"), 0, Decimal("0"), 0)
    # Then 2
    assert isinstance(result[1], Decimal)
    # Then 3
    assert isinstance(result[3], Decimal)


# [claude] PUO-AS-03
def test_puo_as_03__only_w1(db, s):
    """PUO-AS-03 — only W1's POs count, with larger POs in W0 and W2.
    Rules: aggregate_hub_stats R1, R6."""
    po0(db, s, "PO-2026-001", total_amount=Decimal("1000.00"))
    po(db, s, "PO-2026-001", total_amount=Decimal("25.50"))
    po2(db, s, "PO-2026-001", total_amount=Decimal("700.00"))
    result = stats(db, s.W1)
    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == Decimal("25.50")
    # Then 3
    assert result[4] == 1


# [claude] PUO-AS-04
def test_puo_as_04__default_excludes(db, s):
    """PUO-AS-04 — by default voided and fully closed POs add nothing.
    Rules: aggregate_hub_stats R1; _apply… R10."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-002", total_amount=Decimal("20.00"), **closed(s))
    po(db, s, "PO-2026-003", total_amount=Decimal("40.00"), **voided(s))
    result = stats(db, s.W1)
    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == Decimal("10.00")
    # Then 3
    assert result[4] == 1


# [claude] PUO-AS-05
def test_puo_as_05__account_filter(db, s):
    """PUO-AS-05 — the account filter applies, with a lower and a higher account beside it.
    Rules: aggregate_hub_stats R1."""
    po(db, s, "PO-2026-001", total_amount=Decimal("20.00"), account_id=s.AL1.id)
    po(db, s, "PO-2026-002", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-003", total_amount=Decimal("40.00"), account_id=s.AH1.id)
    result = stats(db, s.W1, account_id=s.A1.id)
    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == Decimal("10.00")


# [claude] PUO-AS-06
def test_puo_as_06__joins_count_once(db, s):
    """PUO-AS-06 — with search, invoice and stage joins each PO counts once.
    Rules: aggregate_hub_stats R1; _apply… R13."""
    po(
        db,
        s,
        "PO-2026-417",
        total_amount=Decimal("10.00"),
        **stage(s.SP1),
        invoice_id=s.V1.id,
    )
    po(
        db,
        s,
        "PO-2026-418",
        total_amount=Decimal("20.00"),
        **stage(s.SR1),
        invoice_id=s.V2.id,
    )
    result = stats(
        db, s.W1, search="Northwind", invoice_filter="invoiced", exclude_complete=True
    )
    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == Decimal("30.00")
    # Then 3
    assert result[4] == 0


# [claude] PUO-AS-07
def test_puo_as_07__largest_amounts_sum_exactly(db, s):
    """PUO-AS-07 — the largest stored amounts sum exactly.
    Rules: aggregate_hub_stats R6; HR-15."""
    po(db, s, "PO-2026-001", total_amount=Decimal("9999999999999.99"))
    po(db, s, "PO-2026-002", total_amount=Decimal("0.01"))
    result = stats(db, s.W1)
    # Then 1
    assert result[1] == Decimal("10000000000000.00")


# [claude] PUO-AS-08
def test_puo_as_08__stored_half_up_summed_exactly(db, s):
    """PUO-AS-08 — amounts are stored half up and summed exactly.
    Rules: aggregate_hub_stats R6; Model facts (total_amount Numeric(15, 2)); HR-15."""
    o1 = po(db, s, "PO-2026-001", total_amount=Decimal("2.125"))
    o2 = po(db, s, "PO-2026-002", total_amount=Decimal("0.005"))
    o3 = po(db, s, "PO-2026-003", total_amount=Decimal("-1.005"))
    o1_id, o2_id, o3_id = o1.id, o2.id, o3.id
    db.expire_all()
    result = stats(db, s.W1)
    # Then 1
    assert result[1] == Decimal("1.13")
    # Then 2
    assert reread_po(db, o1_id).total_amount == Decimal("2.13")
    # Then 3
    assert reread_po(db, o2_id).total_amount == Decimal("0.01")
    # Then 4
    assert reread_po(db, o3_id).total_amount == Decimal("-1.01")


# [claude] PUO-AS-09
def test_puo_as_09__writes_nothing(db, s):
    """PUO-AS-09 — writes nothing and takes no lock.
    Rules: aggregate_hub_stats Side effects."""
    o1 = po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = stats(db, s.W1)
    # Then 1
    assert result[0] == 1
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# [claude] PUO-AS-10
def test_puo_as_10__voided_counts_in_counts(db, s):
    """PUO-AS-10 — a shown voided PO counts in total count and, with no invoice, in not-invoiced count.
    Rules: aggregate_hub_stats R1, R3b, R4."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"), invoice_id=s.V1.id)
    po(db, s, "PO-2026-002", total_amount=Decimal("40.00"), **voided(s))
    po(db, s, "PO-2026-003", total_amount=Decimal("5.00"))
    result = stats(db, s.W1, exclude_voided=False)
    # Then 1
    assert result[0] == 3
    # Then 2
    assert result[4] == 2


# =========================================================================== #
# PurchaseOrderDAO.list_for_destination
# =========================================================================== #


def for_dest(db, ws, dtype, did):
    return dao.list_for_destination(
        db, workspace_id=ws.id, destination_type=dtype, destination_id=did
    )


# [claude] PUO-LD-01
def test_puo_ld_01__exact_type_and_id(db, s):
    """PUO-LD-01 — exactly that type and id, not a lower or higher factory, not another type with the same id.
    Rules: list_for_destination R1."""
    po(db, s, "PO-2026-101", **to_storage(s.FA))
    o2 = po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103", **to_storage(s.FZ))
    po(db, s, "PO-2026-104", destination_type="machine", destination_id=s.F1.id)
    result = for_dest(db, s.W1, "storage", s.F1.id)
    # Then 1
    assert ids(result) == [o2.id]


# [claude] PUO-LD-02
def test_puo_ld_02__every_status(db, s):
    """PUO-LD-02 — every status is returned, voided and fully closed included.
    Rules: list_for_destination R1."""
    o1 = po(db, s, "PO-2026-101", **closed(s))
    o2 = po(db, s, "PO-2026-102", **voided(s))
    o3 = po(db, s, "PO-2026-103", **stage(s.SR1))
    result = for_dest(db, s.W1, "storage", s.F1.id)
    # Then 1
    assert idset(result) == {o1.id, o2.id, o3.id}


# [claude] PUO-LD-03
def test_puo_ld_03__newest_first(db, s):
    """PUO-LD-03 — newest created_at first, though ids run otherwise.
    Rules: list_for_destination R2."""
    o1 = po(db, s, "PO-2026-101", created_at=T2, **to_machine(s.M1))
    o2 = po(db, s, "PO-2026-102", created_at=T4, **to_machine(s.M1))
    o3 = po(db, s, "PO-2026-103", created_at=T1, **to_machine(s.M1))
    result = for_dest(db, s.W1, "machine", s.M1.id)
    # Then 1
    assert ids(result) == [o2.id, o1.id, o3.id]


# [claude] PUO-LD-04
def test_puo_ld_04__w2_destination_not_for_w1(db, s):
    """PUO-LD-04 — asked in W1 for W2's destination, W2's PO is not returned.
    Rules: list_for_destination R3."""
    po(db, s, "PO-2026-101")
    po2(db, s, "PO-2026-101")
    result = for_dest(db, s.W1, "storage", s.F2.id)
    # Then 1
    assert result == []


# [claude] PUO-LD-05
def test_puo_ld_05__w0_destination_not_for_w1(db, s):
    """PUO-LD-05 — asked in W1 for W0's destination, W0's PO is not returned.
    Rules: list_for_destination R3."""
    po0(db, s, "PO-2026-101")
    po(db, s, "PO-2026-101")
    result = for_dest(db, s.W1, "storage", s.F0.id)
    # Then 1
    assert result == []


# [claude] PUO-LD-06
def test_puo_ld_06__w2_own_po(db, s):
    """PUO-LD-06 — asked in W2, W2's own PO is returned.
    Rules: list_for_destination R1, R3."""
    po0(db, s, "PO-2026-101")
    po(db, s, "PO-2026-101")
    x2 = po2(db, s, "PO-2026-101")
    result = for_dest(db, s.W2, "storage", s.F2.id)
    # Then 1
    assert ids(result) == [x2.id]


# [claude] PUO-LD-07
def test_puo_ld_07__type_compared_exactly(db, s):
    """PUO-LD-07 — destination_type is compared exactly.
    Rules: list_for_destination R1."""
    po(db, s, "PO-2026-101")
    result = for_dest(db, s.W1, "Storage", s.F1.id)
    # Then 1
    assert result == []


# [claude] PUO-LD-08
def test_puo_ld_08__not_paged(db, s):
    """PUO-LD-08 — not paged: 101 POs are all returned.
    Rules: list_for_destination R2."""
    r = pos(db, s, 101)
    result = for_dest(db, s.W1, "storage", s.F1.id)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].id == r[100].id


# [claude] PUO-LD-09
def test_puo_ld_09__writes_nothing(db, s):
    """PUO-LD-09 — writes nothing and takes no lock.
    Rules: list_for_destination Side effects."""
    o1 = po(db, s, "PO-2026-001")
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = for_dest(db, s.W1, "storage", s.F1.id)
    # Then 1
    assert ids(result) == [o1.id]
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# [claude] PUO-LD-10
def test_puo_ld_10__status_loaded(db, s):
    """PUO-LD-10 — the current status comes loaded with each PO.
    Rules: list_for_destination R1."""
    po(db, s, "PO-2026-101", **stage(s.SR1))
    db.expunge_all()
    result = for_dest(db, s.W1, "storage", s.F1.id)
    # Then 1
    assert "current_status" not in sa_inspect(result[0]).unloaded
    # Then 2
    assert result[0].current_status.name == "Receiving"


# =========================================================================== #
# PurchaseOrderDAO.get_by_id_and_workspace
# =========================================================================== #


# [claude] PUO-GI-01
def test_puo_gi_01__returns_the_po(db, s):
    """PUO-GI-01 — returns the PO, with lower and higher ids beside it.
    Rules: get_by_id_and_workspace R1."""
    po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103")
    result = dao.get_by_id_and_workspace(db, id=o2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, PurchaseOrder)
    # Then 2
    assert result.id == o2.id
    # Then 3
    assert result.po_number == "PO-2026-102"


# [claude] PUO-GI-02
def test_puo_gi_02__voided_returned(db, s):
    """PUO-GI-02 — a voided PO is returned.
    Rules: get_by_id_and_workspace R1."""
    o1 = po(db, s, "PO-2026-101", **voided(s))
    result = dao.get_by_id_and_workspace(db, id=o1.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == o1.id
    # Then 2
    assert result.voided is True


# [claude] PUO-GI-03
def test_puo_gi_03__w0_po_not_for_w1(db, s):
    """PUO-GI-03 — W0's PO is not returned for W1.
    Rules: get_by_id_and_workspace R2."""
    x0 = po0(db, s, "PO-2026-101")
    po(db, s, "PO-2026-101")
    result = dao.get_by_id_and_workspace(db, id=x0.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GI-04
def test_puo_gi_04__w2_po_not_for_w1(db, s):
    """PUO-GI-04 — W2's PO is not returned for W1.
    Rules: get_by_id_and_workspace R2."""
    po(db, s, "PO-2026-101")
    x2 = po2(db, s, "PO-2026-101")
    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GI-05
def test_puo_gi_05__asked_for_w2(db, s):
    """PUO-GI-05 — asked for W2, W2's PO is returned.
    Rules: get_by_id_and_workspace R1, R2."""
    po(db, s, "PO-2026-101")
    x2 = po2(db, s, "PO-2026-101")
    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=s.W2.id)
    # Then 1
    assert result.id == x2.id


# [claude] PUO-GI-06
def test_puo_gi_06__unknown_id(db, s):
    """PUO-GI-06 — an unknown id returns None.
    Rules: get_by_id_and_workspace R2."""
    po(db, s, "PO-2026-101")
    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GI-07
def test_puo_gi_07__no_lock_writes_nothing(db, s):
    """PUO-GI-07 — no row lock, writes nothing.
    Rules: get_by_id_and_workspace R3, Side effects."""
    o1 = po(db, s, "PO-2026-101")
    o1_id = o1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = dao.get_by_id_and_workspace(db, id=o1_id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == o1_id
    # Then 2
    assert "FOR UPDATE" not in rec.sql
    # Then 3
    assert rec.written == []


# [claude] PUO-GI-08
def test_puo_gi_08__status_loaded(db, s):
    """PUO-GI-08 — the current status comes loaded.
    Rules: get_by_id_and_workspace R1."""
    o1 = po(db, s, "PO-2026-101", **stage(s.SP1))
    o1_id = o1.id
    db.expunge_all()
    result = dao.get_by_id_and_workspace(db, id=o1_id, workspace_id=s.W1.id)
    # Then 1
    assert "current_status" not in sa_inspect(result).unloaded
    # Then 2
    assert result.current_status.name == "Planning"


# =========================================================================== #
# PurchaseOrderDAO.get_by_invoice_id
# =========================================================================== #


# [claude] PUO-GV-01
def test_puo_gv_01__po_of_the_invoice(db, s):
    """PUO-GV-01 — returns the PO of the invoice, with the invoice in the middle.
    Rules: get_by_invoice_id R1."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    o2 = po(db, s, "PO-2026-102", invoice_id=s.V2.id)
    po(db, s, "PO-2026-103", invoice_id=s.V3.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, PurchaseOrder)
    # Then 2
    assert result.id == o2.id


# [claude] PUO-GV-02
def test_puo_gv_02__w0_invoice_not_for_w1(db, s):
    """PUO-GV-02 — W0's PO on its own invoice is not returned for W1.
    Rules: get_by_invoice_id R2."""
    po0(db, s, "PO-2026-101", invoice_id=s.V0.id)
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V0.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GV-03
def test_puo_gv_03__w2_invoice_not_for_w1(db, s):
    """PUO-GV-03 — W2's PO on its own invoice is not returned for W1.
    Rules: get_by_invoice_id R2."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po2(db, s, "PO-2026-101", invoice_id=s.V9.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V9.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GV-04
def test_puo_gv_04__asked_for_w2(db, s):
    """PUO-GV-04 — asked for W2, its own PO is returned.
    Rules: get_by_invoice_id R1, R2."""
    po0(db, s, "PO-2026-101", invoice_id=s.V0.id)
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    x2 = po2(db, s, "PO-2026-101", invoice_id=s.V9.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V9.id, workspace_id=s.W2.id)
    # Then 1
    assert result.id == x2.id


# [claude] PUO-GV-05
def test_puo_gv_05__invoice_without_po(db, s):
    """PUO-GV-05 — an invoice with no PO returns None.
    Rules: get_by_invoice_id R2."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GV-06
def test_puo_gv_06__two_pos_one_returned(db, s):
    """PUO-GV-06 — with two POs on one invoice, one of them is returned.
    Rules: get_by_invoice_id R1, R3."""
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V2.id)
    o2 = po(db, s, "PO-2026-102", invoice_id=s.V2.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id in {o1.id, o2.id}


# [claude] PUO-GV-07
@pytest.mark.xfail(strict=False, reason=B2637)
def test_puo_gv_07__lowest_id_after_update(db, s):
    """PUO-GV-07 — on two POs of one invoice the lowest id wins, also after the lower one was updated.
    Rules: get_by_invoice_id R3 [BUG-2637]."""
    o1 = po(db, s, "PO-2026-102", invoice_id=s.V2.id)
    po(db, s, "PO-2026-101", invoice_id=s.V2.id)
    o1_id = o1.id
    seqscan(db)
    bump_p(db, o1)
    result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is not None
    # Then 2
    assert result.id == o1_id


# [claude] PUO-GV-08
@pytest.mark.xfail(strict=False, reason=B2637)
def test_puo_gv_08__lowest_id_when_higher_inserted_first(db, s):
    """PUO-GV-08 — on two POs of one invoice the lowest id wins, when the higher id was inserted first.
    Rules: get_by_invoice_id R3 [BUG-2637]."""
    po(db, s, "PO-2026-101", invoice_id=s.V2.id, id="HIGH")
    ol = po(db, s, "PO-2026-102", invoice_id=s.V2.id)
    seqscan(db)
    result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is not None
    # Then 2
    assert result.id == ol.id


# [claude] PUO-GV-09
@pytest.mark.xfail(strict=True, reason=B2637)
def test_puo_gv_09__orders_by_id_asc(db, s):
    """PUO-GV-09 — the lookup orders by purchase_orders.id ascending.
    Rules: get_by_invoice_id R3 [BUG-2637]."""
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V2.id)
    with Recorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=s.V2.id, workspace_id=s.W1.id)
    op = order_part(rec.sql)
    # Then 1
    assert result.id == o1.id
    # Then 2
    assert "purchase_orders.id" in op
    # Then 3
    assert "DESC" not in op.upper()


# [claude] PUO-GV-10
def test_puo_gv_10__none_gives_po_without_invoice(db, s):
    """PUO-GV-10 — invoice_id None returns the workspace's PO without an invoice.
    Rules: get_by_invoice_id R4."""
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    o2 = po(db, s, "PO-2026-102")
    po(db, s, "PO-2026-103", invoice_id=s.V3.id)
    po2(db, s, "PO-2026-101")
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result.id == o2.id


# [claude] PUO-GV-11
def test_puo_gv_11__none_when_all_invoiced(db, s):
    """PUO-GV-11 — invoice_id None returns None when every PO of the workspace has an invoice.
    Rules: get_by_invoice_id R4."""
    po0(db, s, "PO-2026-101")
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po2(db, s, "PO-2026-101")
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-GV-12
def test_puo_gv_12__no_lock_keeps_pending(db, s):
    """PUO-GV-12 — no row lock, writes nothing, keeps the caller's pending row and edit.
    Rules: get_by_invoice_id Side effects."""
    o1 = po(db, s, "PO-2026-001", invoice_id=s.V1.id)
    p = edit_pending(db, s, o1)
    with Recorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=s.V1.id, workspace_id=s.W1.id)
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
    assert "FOR UPDATE" not in rec.sql
    # Then 7
    assert rec.written == []


# =========================================================================== #
# PurchaseOrderDAO.allocate_po_number
# =========================================================================== #


def w2_numbers(db, s, n):
    """AL-20 / AL-21 Given: W2 holds PO-2031-001 … PO-2031-<n>, one flush."""
    for i in range(1, n + 1):
        db.add(
            PurchaseOrder(
                workspace_id=s.W2.id,
                po_number=f"PO-2031-{i:03d}",
                account_id=s.A2.id,
                destination_type="storage",
                destination_id=s.F2.id,
                subtotal=Decimal("0.00"),
                total_amount=Decimal("0.00"),
                current_status_id=s.SD2.id,
                created_by=s.U1.id,
                created_at=T3,
            )
        )
    db.flush()


# [claude] PUO-AL-01
def test_puo_al_01__first_number(db, s):
    """PUO-AL-01 — no PO yet gives PO-2031-001.
    Rules: allocate_po_number R1, R2, Returns."""
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "PO-2031-001"


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        pytest.param(["PO-2031-007"], "PO-2031-008", id="PUO-AL-02"),
        pytest.param(
            ["PO-2031-003", "PO-2031-007", "PO-2031-005"], "PO-2031-008", id="PUO-AL-03"
        ),
        pytest.param(["PO-2031-999", "PO-2031-1000"], "PO-2031-1001", id="PUO-AL-04"),
        pytest.param(["PO-2031-998"], "PO-2031-999", id="PUO-AL-05"),
        pytest.param(["PO-2031-999"], "PO-2031-1000", id="PUO-AL-06"),
        pytest.param(["PO-2031-9999"], "PO-2031-10000", id="PUO-AL-07"),
        pytest.param(["PO-2031-abc"], "PO-2031-001", id="PUO-AL-08"),
        pytest.param(["PO-2031-004", "PO-2031-abc"], "PO-2031-005", id="PUO-AL-09"),
        pytest.param(["PO-2031-1-2"], "PO-2031-003", id="PUO-AL-10"),
        pytest.param(["PO-2030-050", "PO-2032-060"], "PO-2031-001", id="PUO-AL-11"),
        pytest.param(["po-2031-050"], "PO-2031-001", id="PUO-AL-12"),
        pytest.param(["X-PO-2031-050"], "PO-2031-001", id="PUO-AL-13"),
        pytest.param(["PO-20311-050"], "PO-2031-001", id="PUO-AL-14"),
    ],
)
# [claude] PUO-AL-02 … AL-14
def test_puo_al_02_to_14__next_from_w1_numbers(db, s, numbers, expected):
    """PUO-AL-02 … AL-14 — the next number from W1's stored numbers (highest numeric suffix
    after the last dash, this year's exact prefix only).
    Rules: allocate_po_number R2, R3, Returns."""
    for number in numbers:
        po(db, s, number)
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == expected


# [claude] PUO-AL-15
def test_puo_al_15__other_workspaces_do_not_raise(db, s):
    """PUO-AL-15 — W0's and W2's higher numbers do not raise W1's next number.
    Rules: allocate_po_number R2, R5."""
    po0(db, s, "PO-2031-020")
    po(db, s, "PO-2031-004")
    po2(db, s, "PO-2031-030")
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "PO-2031-005"


# [claude] PUO-AL-16
def test_puo_al_16__asked_for_w2(db, s):
    """PUO-AL-16 — asked for W2, W2's own numbers count.
    Rules: allocate_po_number R2, R5."""
    po0(db, s, "PO-2031-007")
    po(db, s, "PO-2031-010")
    po2(db, s, "PO-2031-003")
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W2.id)
    # Then 1
    assert result == "PO-2031-004"


# [claude] PUO-AL-17
@pytest.mark.xfail(strict=True, reason=B2630)
def test_puo_al_17__w2_001_does_not_move_w1(db, s):
    """PUO-AL-17 — W2 holding PO-2031-001 does not move W1's first number.
    Rules: allocate_po_number R5 [BUG-2630]."""
    po2(db, s, "PO-2031-001")
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result.startswith("PO-2031-")
    # Then 2
    assert result == "PO-2031-001"


# [claude] PUO-AL-18
@pytest.mark.xfail(strict=True, reason=B2630)
def test_puo_al_18__w0_001_does_not_move_w1(db, s):
    """PUO-AL-18 — W0 holding PO-2031-001 does not move W1's first number.
    Rules: allocate_po_number R5 [BUG-2630]."""
    po0(db, s, "PO-2031-001")
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result.startswith("PO-2031-")
    # Then 2
    assert result == "PO-2031-001"


# [claude] PUO-AL-19
@pytest.mark.xfail(strict=True, reason=B2630)
def test_puo_al_19__w2_next_number_not_skipped(db, s):
    """PUO-AL-19 — W2 holding W1's next number does not skip it.
    Rules: allocate_po_number R5 [BUG-2630]."""
    po(db, s, "PO-2031-004")
    po2(db, s, "PO-2031-005")
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result.startswith("PO-2031-")
    # Then 2
    assert result == "PO-2031-005"


# [claude] PUO-AL-20
def test_puo_al_20__1000_taken_raise_500(db, s):
    """PUO-AL-20 — 1000 taken candidates raise 500 (today's path through W2's numbers).
    Rules: allocate_po_number R6; Errors row 1."""
    w2_numbers(db, s, 1000)
    before = totals(db)
    with clock():
        # Then 1
        with pytest.raises(HTTPException) as exc:
            dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 500
    # Then 3
    assert exc.value.detail == "Could not allocate a unique purchase order number"
    # Then 4
    assert totals(db) == before


# [claude] PUO-AL-21
def test_puo_al_21__999_taken_still_give_number(db, s):
    """PUO-AL-21 — 999 taken candidates still give a number (today's path through W2's numbers).
    Rules: allocate_po_number R6."""
    w2_numbers(db, s, 999)
    with clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "PO-2031-1000"


# [claude] PUO-AL-22
def test_puo_al_22__year_from_clock(db, s):
    """PUO-AL-22 — the year comes from the clock: 2033 gives PO-2033-001, 2031 numbers do not count.
    Rules: allocate_po_number R1, R2."""
    po(db, s, "PO-2031-005")
    with clock(datetime(2033, 3, 1, 12, 0), datetime(2033, 3, 1, 12, 0)):
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "PO-2033-001"


# [claude] PUO-AL-23
@pytest.mark.xfail(strict=True, reason=B2632)
def test_puo_al_23__utc_year_when_local_in_next_year(db, s):
    """PUO-AL-23 — the year is UTC's when the local clock is already in the next year.
    Rules: allocate_po_number R1 [BUG-2632]."""
    po(db, s, "PO-2031-004")
    with clock(datetime(2032, 1, 1, 0, 30), datetime(2031, 12, 31, 18, 30)):
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result.startswith("PO-")
    # Then 2
    assert result == "PO-2031-005"


# [claude] PUO-AL-24
@pytest.mark.xfail(strict=True, reason=B2632)
def test_puo_al_24__utc_year_when_local_in_old_year(db, s):
    """PUO-AL-24 — the year is UTC's when the local clock is still in the old year.
    Rules: allocate_po_number R1 [BUG-2632]."""
    po(db, s, "PO-2031-004")
    with clock(datetime(2031, 12, 31, 20, 0), datetime(2032, 1, 1, 2, 0)):
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result.startswith("PO-")
    # Then 2
    assert result == "PO-2032-001"


# [claude] PUO-AL-25
def test_puo_al_25__stores_nothing(db, s):
    """PUO-AL-25 — stores nothing: a pending PO is not counted and stays pending, an edit stays unflushed, no lock.
    Rules: allocate_po_number R4, Side effects."""
    o1 = po(db, s, "PO-2031-002")
    o1.total_amount = Decimal("5.00")
    p = PurchaseOrder(**_po_fields(s, "PO-2031-050"))
    db.add(p)
    with Recorder(db) as rec, clock():
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "PO-2031-003"
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
    # Then 7
    assert all("FOR UPDATE" not in st for st in rec.sqls)


# [claude] PUO-AL-26
def test_puo_al_26__keyword_only(db, s):
    """PUO-AL-26 — keyword-only: a positional workspace id raises TypeError.
    Rules: allocate_po_number signature."""
    with clock():
        # Then 1
        with pytest.raises(TypeError):
            dao.allocate_po_number(db, s.W1.id)


# [claude] PUO-AL-27
def test_puo_al_27__same_number_same_workspace_refused(db, s):
    """PUO-AL-27 — the same number twice in one workspace is refused by the database.
    Rules: Model facts (uq_po_workspace_number); allocate_po_number R7 (today half)."""
    po(db, s, "PO-2031-008")
    o2 = PurchaseOrder(**_po_fields(s, "PO-2031-008"))
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(o2)
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_po_workspace_number" in str(exc.value.orig)


# [claude] PUO-AL-28
def test_puo_al_28__same_number_two_workspaces_accepted(db, s):
    """PUO-AL-28 — the same number in two workspaces is accepted.
    Rules: Model facts (uq_po_workspace_number is per workspace)."""
    po(db, s, "PO-2031-008")
    x2 = PurchaseOrder(
        **{
            **_po_fields(s, "PO-2031-008"),
            "workspace_id": s.W2.id,
            "account_id": s.A2.id,
            "destination_id": s.F2.id,
            "current_status_id": s.SD2.id,
        }
    )
    db.add(x2)
    db.flush()
    # Then 1
    assert x2.id is not None
    # Then 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.po_number == "PO-2031-008")
        )
        == 2
    )


# [claude] PUO-AL-29
@pytest.mark.xfail(strict=True, reason=B2630)
def test_puo_al_29__always_taken_raises_500(db, s):
    """PUO-AL-29 — with the taken check always answering taken, 1000 candidates raise 500.
    Rules: allocate_po_number R6 [BUG-2630]; Errors row 1. Race simulation: `_po_number_taken`."""
    before = totals(db)
    with (
        clock(),
        patch(
            "app.dao.purchase_order._po_number_taken", return_value=True, create=True
        ) as taken,
    ):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 500
    # Then 3
    assert exc.value.detail == "Could not allocate a unique purchase order number"
    # Then 4
    assert taken.call_count == 1000
    # Then 5
    assert taken.call_args_list[0].kwargs["workspace_id"] == s.W1.id
    # Then 6
    assert taken.call_args_list[0].kwargs["po_number"] == "PO-2031-001"
    # Then 7
    assert totals(db) == before


# [claude] PUO-AL-30
@pytest.mark.xfail(strict=True, reason=B2630)
def test_puo_al_30__999_taken_1000th_returned(db, s):
    """PUO-AL-30 — with 999 candidates taken, the 1000th is returned.
    Rules: allocate_po_number R6 [BUG-2630]. Race simulation: `_po_number_taken`."""
    with (
        clock(),
        patch(
            "app.dao.purchase_order._po_number_taken",
            side_effect=[True] * 999 + [False],
            create=True,
        ) as taken,
    ):
        result = dao.allocate_po_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "PO-2031-1000"
    # Then 2
    assert taken.call_count == 1000


# =========================================================================== #
# PurchaseOrderItemDAO.get_by_order
# =========================================================================== #


# [claude] PUO-IO-01
def test_puo_io_01__by_line_number(db, s):
    """PUO-IO-01 — lines by line_number, though inserted out of order.
    Rules: get_by_order R1."""
    o1 = po(db, s, "PO-2026-101")
    l3 = line(db, s, o1, 3, item_id=s.IN1.id)
    l1 = line(db, s, o1, 1)
    l2 = line(db, s, o1, 2, item_id=s.IK.id)
    result = idao.get_by_order(db, purchase_order_id=o1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [l1.id, l2.id, l3.id]


# [claude] PUO-IO-02
def test_puo_io_02__other_pos_not_mixed(db, s):
    """PUO-IO-02 — lines of a lower and a higher PO are not mixed in.
    Rules: get_by_order R1."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103")
    line(db, s, o1, 1)
    lb = line(db, s, o2, 2)
    line(db, s, o3, 1)
    result = idao.get_by_order(db, purchase_order_id=o2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [lb.id]


# [claude] PUO-IO-03
def test_puo_io_03__w0_po_in_w1(db, s):
    """PUO-IO-03 — W0's PO asked in W1 gives nothing.
    Rules: get_by_order R2."""
    x0 = po0(db, s, "PO-2026-101")
    line(db, s, x0, 1)
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = idao.get_by_order(db, purchase_order_id=x0.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PUO-IO-04
def test_puo_io_04__w2_po_in_w1(db, s):
    """PUO-IO-04 — W2's PO asked in W1 gives nothing.
    Rules: get_by_order R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    x2 = po2(db, s, "PO-2026-101")
    line(db, s, x2, 1)
    result = idao.get_by_order(db, purchase_order_id=x2.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PUO-IO-05
def test_puo_io_05__asked_in_w2(db, s):
    """PUO-IO-05 — asked in W2, W2's lines are returned.
    Rules: get_by_order R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    x2 = po2(db, s, "PO-2026-101")
    lx = line(db, s, x2, 1)
    result = idao.get_by_order(db, purchase_order_id=x2.id, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [lx.id]


# [claude] PUO-IO-06
def test_puo_io_06__unknown_po(db, s):
    """PUO-IO-06 — an unknown PO gives nothing.
    Rules: get_by_order R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = idao.get_by_order(db, purchase_order_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PUO-IO-07
def test_puo_io_07__not_paged(db, s):
    """PUO-IO-07 — not paged: 101 lines are all returned.
    Rules: get_by_order R1."""
    o1 = po(db, s, "PO-2026-101")
    for k in range(1, 102):
        db.add(
            PurchaseOrderItem(
                workspace_id=s.W1.id,
                purchase_order_id=o1.id,
                line_number=k,
                item_id=s.I1.id,
                quantity_ordered=Decimal("1.00"),
                quantity_received=Decimal("0.00"),
            )
        )
    db.flush()
    result = idao.get_by_order(db, purchase_order_id=o1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert [r.line_number for r in result] == list(range(1, 102))


# [claude] PUO-IO-08
def test_puo_io_08__query_shape(db, s):
    """PUO-IO-08 — orders by line_number, does not join the PO, takes no lock, writes nothing.
    Rules: get_by_order R1, Side effects."""
    o1 = po(db, s, "PO-2026-101")
    l1 = line(db, s, o1, 1)
    o1_id, l1_id = o1.id, l1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = idao.get_by_order(db, purchase_order_id=o1_id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [l1_id]
    # Then 2
    assert "line_number" in order_part(rec.isql)
    # Then 3
    assert "purchase_orders" not in rec.isql
    # Then 4
    assert "FOR UPDATE" not in rec.isql
    # Then 5
    assert rec.written == []


# =========================================================================== #
# PurchaseOrderItemDAO.get_by_purchase_order_ids
# =========================================================================== #


# [claude] PUO-IP-01
def test_puo_ip_01__empty_list_no_query(db, s):
    """PUO-IP-01 — an empty id list gives [] without a query.
    Rules: get_by_purchase_order_ids R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    with Recorder(db) as rec:
        result = idao.get_by_purchase_order_ids(
            db, workspace_id=s.W1.id, purchase_order_ids=[]
        )
    # Then 1
    assert result == []
    # Then 2
    assert rec.sqls == []


# [claude] PUO-IP-02
def test_puo_ip_02__ordered_by_po_then_line(db, s):
    """PUO-IP-02 — lines ordered by PO id, then line_number; an unasked PO in between is left out.
    Rules: get_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103")
    c1 = line(db, s, o3, 1)
    a2 = line(db, s, o1, 2)
    line(db, s, o2, 1)
    a1 = line(db, s, o1, 1)
    c2 = line(db, s, o3, 2)
    result = idao.get_by_purchase_order_ids(
        db, workspace_id=s.W1.id, purchase_order_ids=[o3.id, o1.id]
    )
    # Then 1
    assert ids(result) == [a1.id, a2.id, c1.id, c2.id]


# [claude] PUO-IP-03
def test_puo_ip_03__other_workspaces_contribute_nothing(db, s):
    """PUO-IP-03 — ids of W0's and W2's POs contribute nothing.
    Rules: get_by_purchase_order_ids R2."""
    x0 = po0(db, s, "PO-2026-101")
    line(db, s, x0, 1)
    o2 = po(db, s, "PO-2026-102")
    l2 = line(db, s, o2, 1)
    x2 = po2(db, s, "PO-2026-101")
    line(db, s, x2, 1)
    result = idao.get_by_purchase_order_ids(
        db, workspace_id=s.W1.id, purchase_order_ids=[x0.id, o2.id, x2.id]
    )
    # Then 1
    assert ids(result) == [l2.id]


# [claude] PUO-IP-04
def test_puo_ip_04__unknown_id(db, s):
    """PUO-IP-04 — an unknown id gives [].
    Rules: get_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = idao.get_by_purchase_order_ids(
        db, workspace_id=s.W1.id, purchase_order_ids=[MISSING]
    )
    # Then 1
    assert result == []


# [claude] PUO-IP-05
def test_puo_ip_05__no_lock_writes_nothing(db, s):
    """PUO-IP-05 — takes no lock and writes nothing.
    Rules: get_by_purchase_order_ids Side effects."""
    o1 = po(db, s, "PO-2026-101")
    l1 = line(db, s, o1, 1)
    o1_id, l1_id = o1.id, l1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = idao.get_by_purchase_order_ids(
            db, workspace_id=s.W1.id, purchase_order_ids=[o1_id]
        )
    # Then 1
    assert ids(result) == [l1_id]
    # Then 2
    assert "FOR UPDATE" not in rec.isql
    # Then 3
    assert rec.written == []


# =========================================================================== #
# PurchaseOrderItemDAO.get_by_id_and_workspace
# =========================================================================== #


# [claude] PUO-IG-01
def test_puo_ig_01__returns_the_line(db, s):
    """PUO-IG-01 — returns the line, with lower and higher line ids beside it.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    l2 = line(db, s, o1, 2, item_id=s.IN1.id)
    line(db, s, o1, 3)
    result = idao.get_by_id_and_workspace(db, id=l2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == l2.id
    # Then 2
    assert result.item_id == s.IN1.id


# [claude] PUO-IG-02
def test_puo_ig_02__w0_line_not_for_w1(db, s):
    """PUO-IG-02 — W0's line is not returned for W1.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    x0 = po0(db, s, "PO-2026-101")
    lx = line(db, s, x0, 1)
    result = idao.get_by_id_and_workspace(db, id=lx.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-IG-03
def test_puo_ig_03__w2_line_not_for_w1(db, s):
    """PUO-IG-03 — W2's line is not returned for W1.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    x2 = po2(db, s, "PO-2026-101")
    lx = line(db, s, x2, 1)
    result = idao.get_by_id_and_workspace(db, id=lx.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-IG-04
def test_puo_ig_04__asked_in_w2(db, s):
    """PUO-IG-04 — asked in W2, W2's line is returned.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    x2 = po2(db, s, "PO-2026-101")
    lx = line(db, s, x2, 1)
    result = idao.get_by_id_and_workspace(db, id=lx.id, workspace_id=s.W2.id)
    # Then 1
    assert result.id == lx.id


# [claude] PUO-IG-05
def test_puo_ig_05__unknown_id(db, s):
    """PUO-IG-05 — an unknown id returns None.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PUO-IG-06
def test_puo_ig_06__no_lock_writes_nothing(db, s):
    """PUO-IG-06 — no row lock, writes nothing.
    Rules: PurchaseOrderItemDAO.get_by_id_and_workspace R1."""
    o1 = po(db, s, "PO-2026-101")
    l1 = line(db, s, o1, 1)
    l1_id = l1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = idao.get_by_id_and_workspace(db, id=l1_id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == l1_id
    # Then 2
    assert "FOR UPDATE" not in rec.isql
    # Then 3
    assert rec.written == []


# =========================================================================== #
# PurchaseOrderItemDAO.summarize_by_purchase_order_ids
# =========================================================================== #


def summarize(db, ws, po_ids):
    return idao.summarize_by_purchase_order_ids(
        db, workspace_id=ws.id, purchase_order_ids=po_ids
    )


# [claude] PUO-IS-01
def test_puo_is_01__empty_list(db, s):
    """PUO-IS-01 — an empty id list gives {}.
    Rules: summarize_by_purchase_order_ids R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = summarize(db, s.W1, [])
    # Then 1
    assert result == {}


# [claude] PUO-IS-02
def test_puo_is_02__only_asked_w1_pos_with_lines(db, s):
    """PUO-IS-02 — only asked POs of W1 with lines get a key.
    Rules: summarize_by_purchase_order_ids R1."""
    x0 = po0(db, s, "PO-2026-101")
    line(db, s, x0, 1)
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    o2 = po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103")
    line(db, s, o3, 1)
    x2 = po2(db, s, "PO-2026-101")
    line(db, s, x2, 1)
    result = summarize(db, s.W1, [x0.id, o1.id, o2.id, x2.id])
    # Then 1
    assert set(result.keys()) == {o1.id}


# [claude] PUO-IS-03
def test_puo_is_03__unknown_id(db, s):
    """PUO-IS-03 — an unknown id gives {}.
    Rules: summarize_by_purchase_order_ids R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = summarize(db, s.W1, [MISSING])
    # Then 1
    assert result == {}


# [claude] PUO-IS-04
def test_puo_is_04__no_lock_writes_nothing(db, s):
    """PUO-IS-04 — takes no lock and writes nothing.
    Rules: summarize_by_purchase_order_ids Side effects."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    with Recorder(db) as rec:
        result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert set(result.keys()) == {o1.id}
    # Then 2
    assert all("FOR UPDATE" not in st for st in rec.sqls)
    # Then 3
    assert rec.written == []


# =========================================================================== #
# PurchaseOrderItemDAO.preview_names_by_purchase_order_ids
# =========================================================================== #


def preview(db, ws, po_ids, **kw):
    return idao.preview_names_by_purchase_order_ids(
        db, workspace_id=ws.id, purchase_order_ids=po_ids, **kw
    )


# [claude] PUO-IN-01
def test_puo_in_01__empty_list(db, s):
    """PUO-IN-01 — an empty id list gives {}.
    Rules: preview_names_by_purchase_order_ids R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = preview(db, s.W1, [])
    # Then 1
    assert result == {}


@pytest.mark.parametrize(
    "limit",
    [pytest.param(0, id="PUO-IN-02"), pytest.param(-1, id="PUO-IN-03")],
)
# [claude] PUO-IN-02, IN-03
def test_puo_in_02_03__limit_zero_or_negative(db, s, limit):
    """PUO-IN-02, IN-03 — limit 0 or a negative limit gives {}.
    Rules: preview_names_by_purchase_order_ids R1."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    result = preview(db, s.W1, [o1.id], limit=limit)
    # Then 1
    assert result == {}


# [claude] PUO-IN-04
def test_puo_in_04__limit_one(db, s):
    """PUO-IN-04 — limit 1 gives the first line's name.
    Rules: preview_names_by_purchase_order_ids R1, R2, R3."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 2, item_id=s.IN1.id)
    line(db, s, o1, 1)
    result = preview(db, s.W1, [o1.id], limit=1)
    # Then 1
    assert result == {o1.id: ["Bolt"]}


def _five_lines(db, s, o1):
    """The Given rows L5, L3, L1, L4, L2 of IN-05 and IN-06."""
    line(db, s, o1, 5, item_id=s.IR.id)
    line(db, s, o1, 3, item_id=s.IK.id)
    line(db, s, o1, 1)
    line(db, s, o1, 4, item_id=s.IW.id)
    line(db, s, o1, 2, item_id=s.IN1.id)


# [claude] PUO-IN-05
def test_puo_in_05__default_first_four(db, s):
    """PUO-IN-05 — by default the first 4 names in line order.
    Rules: preview_names_by_purchase_order_ids R2, R3."""
    o1 = po(db, s, "PO-2026-101")
    _five_lines(db, s, o1)
    result = preview(db, s.W1, [o1.id])
    # Then 1
    assert result == {o1.id: ["Bolt", "Nut", "Steel", "Washer"]}


# [claude] PUO-IN-06
def test_puo_in_06__limit_1000_every_name(db, s):
    """PUO-IN-06 — limit=1000 gives every name.
    Rules: preview_names_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    _five_lines(db, s, o1)
    result = preview(db, s.W1, [o1.id], limit=1000)
    # Then 1
    assert result == {o1.id: ["Bolt", "Nut", "Steel", "Washer", "Rivet"]}


# [claude] PUO-IN-07
def test_puo_in_07__same_item_twice(db, s):
    """PUO-IN-07 — the same item on two lines gives its name twice.
    Rules: preview_names_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    line(db, s, o1, 2)
    result = preview(db, s.W1, [o1.id])
    # Then 1
    assert result == {o1.id: ["Bolt", "Bolt"]}


# [claude] PUO-IN-08
def test_puo_in_08__empty_name_shows_item_id(db, s):
    """PUO-IN-08 — an item with an empty name shows as Item #id.
    Rules: preview_names_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1, item_id=s.IE.id)
    line(db, s, o1, 2)
    result = preview(db, s.W1, [o1.id])
    # Then 1
    assert result == {o1.id: [f"Item #{s.IE.id}", "Bolt"]}


# [claude] PUO-IN-09
def test_puo_in_09__limit_per_po(db, s):
    """PUO-IN-09 — the limit applies per PO; POs without lines and other workspaces' POs get no key.
    Rules: preview_names_by_purchase_order_ids R2."""
    x0 = po0(db, s, "PO-2026-101")
    line(db, s, x0, 1)
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    line(db, s, o1, 2, item_id=s.IN1.id)
    line(db, s, o1, 3, item_id=s.IK.id)
    o2 = po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103")
    line(db, s, o3, 1, item_id=s.IW.id)
    line(db, s, o3, 2, item_id=s.IR.id)
    line(db, s, o3, 3)
    x2 = po2(db, s, "PO-2026-101")
    line(db, s, x2, 1)
    result = preview(db, s.W1, [x0.id, o1.id, o2.id, o3.id, x2.id], limit=2)
    # Then 1
    assert result == {o1.id: ["Bolt", "Nut"], o3.id: ["Washer", "Rivet"]}


# [claude] PUO-IN-10
@pytest.mark.xfail(strict=False, reason=B2638)
def test_puo_in_10__line_tie_lower_id_first_after_update(db, s):
    """PUO-IN-10 — lines sharing a line number come lower id first, after the lowest id was updated.
    Rules: preview_names_by_purchase_order_ids R3 [BUG-2638]."""
    o1 = po(db, s, "PO-2026-101")
    la = line(db, s, o1, 1, item_id=s.IN1.id)
    line(db, s, o1, 1)
    line(db, s, o1, 1, item_id=s.IK.id)
    o1_id = o1.id
    seqscan(db)
    bump_l(db, la)
    result = preview(db, s.W1, [o1_id])
    # Then 1
    assert len(result[o1_id]) == 3
    # Then 2
    assert result[o1_id] == ["Nut", "Bolt", "Steel"]


# [claude] PUO-IN-11
@pytest.mark.xfail(strict=False, reason=B2638)
def test_puo_in_11__line_tie_high_id_last(db, s):
    """PUO-IN-11 — lines sharing a line number: a high explicit id comes last.
    Rules: preview_names_by_purchase_order_ids R3 [BUG-2638]."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    line(db, s, o1, 1, item_id=s.IN1.id, id="HIGH")
    line(db, s, o1, 1, item_id=s.IK.id)
    result = preview(db, s.W1, [o1.id])
    # Then 1
    assert len(result[o1.id]) == 3
    # Then 2
    assert result[o1.id] == ["Bolt", "Steel", "Nut"]


# [claude] PUO-IN-12
@pytest.mark.xfail(strict=True, reason=B2638)
def test_puo_in_12__query_breaks_ties_by_id(db, s):
    """PUO-IN-12 — the preview query breaks line-number ties by line id.
    Rules: preview_names_by_purchase_order_ids R3 [BUG-2638]."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    with Recorder(db) as rec:
        result = preview(db, s.W1, [o1.id])
    op = order_part(rec.isql)
    # Then 1
    assert result == {o1.id: ["Bolt"]}
    # Then 2
    assert "line_number" in op
    # Then 3
    assert "purchase_order_items.id" in op
    # Then 4
    assert op.index("line_number") < op.index("purchase_order_items.id")


# [claude] PUO-IN-13
def test_puo_in_13__no_lock_writes_nothing(db, s):
    """PUO-IN-13 — takes no lock and writes nothing.
    Rules: preview_names_by_purchase_order_ids Side effects."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    with Recorder(db) as rec:
        result = preview(db, s.W1, [o1.id])
    # Then 1
    assert result == {o1.id: ["Bolt"]}
    # Then 2
    assert all("FOR UPDATE" not in st for st in rec.sqls)
    # Then 3
    assert rec.written == []


# =========================================================================== #
# aggregate_hub_stats — voided POs (BUG-2639, owner OQ-35)
# =========================================================================== #


# [claude] PUO-OQ35-01
@pytest.mark.xfail(strict=True, reason=B2639)
def test_puo_oq35_01__verified_example(db, s):
    """PUO-OQ35-01 — the verified example: (6, 606.00, 4, 506.00, 3) with a voided 400.00.
    Rules: aggregate_hub_stats R1, R2 [BUG-2639], R3, R3a [BUG-2639], R4."""
    po(
        db,
        s,
        "PO-2026-001",
        total_amount=Decimal("100.00"),
        **closed(s),
        invoice_id=s.V1.id,
    )
    po(
        db,
        s,
        "PO-2026-002",
        total_amount=Decimal("200.00"),
        **stage(s.SC1),
        invoice_id=s.V2.id,
    )
    po(db, s, "PO-2026-003", total_amount=Decimal("300.00"), invoice_id=s.V3.id)
    po(db, s, "PO-2026-004", total_amount=Decimal("400.00"), **voided(s))
    po(db, s, "PO-2026-005", total_amount=Decimal("1.00"))
    po(db, s, "PO-2026-006", total_amount=Decimal("5.00"))
    result = stats(db, s.W1, exclude_complete=False, exclude_voided=False)
    # Then 1
    assert result[0] == 6
    # Then 2
    assert result[4] == 3
    # Then 3
    assert result[1] == Decimal("606.00")
    # Then 4
    assert result[2] == 4
    # Then 5
    assert result[3] == Decimal("506.00")


# [claude] PUO-OQ35-02
@pytest.mark.xfail(strict=True, reason=B2639)
def test_puo_oq35_02__voided_adds_no_value(db, s):
    """PUO-OQ35-02 — a shown voided PO counts in total count but adds nothing to total value.
    Rules: aggregate_hub_stats R1, R2 [BUG-2639], R3b."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-002", total_amount=Decimal("40.00"), **voided(s))
    result = stats(db, s.W1, exclude_voided=False)
    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == Decimal("10.00")


# [claude] PUO-OQ35-03
@pytest.mark.xfail(strict=True, reason=B2639)
def test_puo_oq35_03__voided_never_open(db, s):
    """PUO-OQ35-03 — a shown voided PO is never open.
    Rules: aggregate_hub_stats R3a [BUG-2639]."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-002", total_amount=Decimal("40.00"), **voided(s))
    result = stats(db, s.W1, exclude_voided=False)
    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[2] == 1
    # Then 3
    assert result[3] == Decimal("10.00")


# [claude] PUO-OQ35-04
@pytest.mark.xfail(strict=True, reason=B2639)
def test_puo_oq35_04__voided_closed_adds_nothing(db, s):
    """PUO-OQ35-04 — a voided PO marked Complete and paid adds nothing either (legacy data).
    Rules: aggregate_hub_stats R2 [BUG-2639], R3; _purchase_order_is_fully_closed_clause R1."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-002", total_amount=Decimal("40.00"), **closed(s), **voided(s))
    result = stats(db, s.W1, exclude_complete=False, exclude_voided=False)
    # Then 1
    assert result[2] == 1
    # Then 2
    assert result[3] == Decimal("10.00")
    # Then 3
    assert result[1] == Decimal("10.00")


# =========================================================================== #
# aggregate_hub_stats — open count and open value (owner OQ-36, intended)
# =========================================================================== #


# [claude] PUO-OQ36-01
def test_puo_oq36_01__complete_unpaid_open(db, s):
    """PUO-OQ36-01 — a Complete unpaid PO is open with its full total.
    Rules: aggregate_hub_stats R3."""
    po(
        db,
        s,
        "PO-2026-001",
        total_amount=Decimal("200.00"),
        **stage(s.SC1),
        invoice_id=s.V1.id,
    )
    result = stats(db, s.W1, exclude_complete=False)
    # Then 1
    assert result[2] == 1
    # Then 2
    assert result[3] == Decimal("200.00")


# [claude] PUO-OQ36-02
def test_puo_oq36_02__paid_receiving_open(db, s):
    """PUO-OQ36-02 — a paid PO still in Receiving is open with its full total.
    Rules: aggregate_hub_stats R3."""
    po(db, s, "PO-2026-001", total_amount=Decimal("300.00"), **stage(s.SR1), paid=True)
    result = stats(db, s.W1, exclude_complete=False)
    # Then 1
    assert result[2] == 1
    # Then 2
    assert result[3] == Decimal("300.00")


# [claude] PUO-OQ36-03
def test_puo_oq36_03__closed_in_totals_not_open(db, s):
    """PUO-OQ36-03 — a Complete and paid PO counts in the totals but is not open.
    Rules: aggregate_hub_stats R1, R3."""
    po(db, s, "PO-2026-001", total_amount=Decimal("100.00"), **closed(s))
    po(db, s, "PO-2026-002", total_amount=Decimal("5.00"))
    result = stats(db, s.W1, exclude_complete=False)
    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == Decimal("105.00")
    # Then 3
    assert result[2] == 1
    # Then 4
    assert result[3] == Decimal("5.00")


# [claude] PUO-OQ36-04
def test_puo_oq36_04__open_value_exact(db, s):
    """PUO-OQ36-04 — open value is an exact sum.
    Rules: aggregate_hub_stats R3, R6."""
    po(db, s, "PO-2026-001", total_amount=Decimal("0.10"))
    po(db, s, "PO-2026-002", total_amount=Decimal("0.20"), **stage(s.SP1))
    po(db, s, "PO-2026-003", total_amount=Decimal("0.30"), **stage(s.SR1))
    result = stats(db, s.W1)
    # Then 1
    assert result[2] == 3
    # Then 2
    assert result[3] == Decimal("0.60")
    # Then 3
    assert isinstance(result[3], Decimal)


# [claude] PUO-OQ36-05
def test_puo_oq36_05__default_filters_every_counted_open(db, s):
    """PUO-OQ36-05 — with the default filters every counted PO is open.
    Rules: aggregate_hub_stats R3; _apply… R10."""
    po(db, s, "PO-2026-001", total_amount=Decimal("10.00"))
    po(db, s, "PO-2026-002", total_amount=Decimal("20.00"), **stage(s.SC1))
    po(db, s, "PO-2026-003", total_amount=Decimal("100.00"), **closed(s))
    result = stats(db, s.W1)
    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[2] == 2
    # Then 3
    assert result[3] == Decimal("30.00")


# [claude] PUO-OQ36-06
def test_puo_oq36_06__no_open_po(db, s):
    """PUO-OQ36-06 — no open PO gives open count 0 and open value 0.
    Rules: aggregate_hub_stats R3, R5."""
    po(db, s, "PO-2026-001", total_amount=Decimal("100.00"), **closed(s))
    result = stats(db, s.W1, exclude_complete=False)
    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[2] == 0
    # Then 3
    assert result[3] == Decimal("0")


# =========================================================================== #
# _apply_purchase_order_hub_filters — outstanding payment (BUG-2640, owner OQ-37)
# =========================================================================== #

# Convention "VX" (a real invoice void) and "VXP" (legacy voided-and-paid)
VX_COLS = {
    "invoice_status": "voided",
    "void_note": "Entered twice",
    "paid_amount": Decimal("0.00"),
    "payment_status": "unpaid",
}
VXP_COLS = {
    "invoice_status": "voided",
    "payment_status": "paid",
    "paid_amount": Decimal("100.00"),
}
VP_COLS = {"payment_status": "paid", "paid_amount": Decimal("100.00")}


# [claude] PUO-OQ37-01
def test_puo_oq37_01__confirmed_unpaid_outstanding(db, s):
    """PUO-OQ37-01 — a confirmed unpaid invoice is outstanding; a paid invoice and no invoice are not.
    Rules: _apply… R9 [BUG-2640]."""
    vp = inv1(db, s, **VP_COLS)
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po(db, s, "PO-2026-102", invoice_id=vp.id)
    po(db, s, "PO-2026-103")
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-OQ37-02
@pytest.mark.xfail(strict=True, reason=B2640)
def test_puo_oq37_02__draft_invoice_not_outstanding(db, s):
    """PUO-OQ37-02 — a PO whose invoice is a draft is not outstanding.
    Rules: _apply… R9 [BUG-2640]."""
    vd = inv1(db, s, invoice_status="draft")
    po(db, s, "PO-2026-101", invoice_id=vd.id)
    po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103", invoice_id=s.V1.id)
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert o3.id in idset(result)
    # Then 2
    assert idset(result) == {o3.id}


# [claude] PUO-OQ37-03
@pytest.mark.xfail(strict=True, reason=B2640)
def test_puo_oq37_03__voided_invoice_not_outstanding(db, s):
    """PUO-OQ37-03 — a PO whose invoice was voided (reset to unpaid) is not outstanding.
    Rules: _apply… R9 [BUG-2640]."""
    vx = inv1(db, s, **VX_COLS)
    po(db, s, "PO-2026-101", invoice_id=vx.id)
    po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103", invoice_id=s.V1.id)
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert o3.id in idset(result)
    # Then 2
    assert idset(result) == {o3.id}


# [claude] PUO-OQ37-04
def test_puo_oq37_04__voided_paid_invoice_not_outstanding(db, s):
    """PUO-OQ37-04 — a PO whose voided invoice is marked paid is not outstanding (legacy data).
    Rules: _apply… R9 [BUG-2640]."""
    vxp = inv1(db, s, **VXP_COLS)
    po(db, s, "PO-2026-101", invoice_id=vxp.id)
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert result == []


# [claude] PUO-OQ37-05
@pytest.mark.xfail(strict=True, reason=B2640)
def test_puo_oq37_05__count_only_confirmed_unpaid(db, s):
    """PUO-OQ37-05 — count_for_hub counts only the confirmed unpaid PO.
    Rules: _apply… R9 [BUG-2640]; count_for_hub R1."""
    vd = inv1(db, s, invoice_status="draft")
    vx = inv1(db, s, **VX_COLS)
    vp = inv1(db, s, **VP_COLS)
    po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po(db, s, "PO-2026-102", invoice_id=vd.id)
    po(db, s, "PO-2026-103", invoice_id=vx.id)
    po(db, s, "PO-2026-104", invoice_id=vp.id)
    po(db, s, "PO-2026-105")
    result = dao.count_for_hub(
        db, workspace_id=s.W1.id, invoice_filter="outstanding_payment"
    )
    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 1


# [claude] PUO-OQ37-06
def test_puo_oq37_06__other_workspaces_not_listed(db, s):
    """PUO-OQ37-06 — W0's and W2's outstanding POs are not listed for W1.
    Rules: _apply… R9 [BUG-2640], R1."""
    po0(db, s, "PO-2026-101", invoice_id=s.V0.id)
    o1 = po(db, s, "PO-2026-101", invoice_id=s.V1.id)
    po2(db, s, "PO-2026-101", invoice_id=s.V9.id)
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert idset(result) == {o1.id}


# [claude] PUO-OQ37-07
def test_puo_oq37_07__locked_partial_overdue_outstanding(db, s):
    """PUO-OQ37-07 — locked unpaid, confirmed partial and confirmed overdue are outstanding; confirmed paid is not.
    Rules: _apply… R9 [BUG-2640]."""
    vl = inv1(db, s, invoice_status="locked")
    vpa = inv1(db, s, payment_status="partial", paid_amount=Decimal("40.00"))
    vo = inv1(db, s, payment_status="overdue")
    vp = inv1(db, s, **VP_COLS)
    o1 = po(db, s, "PO-2026-101", invoice_id=vl.id)
    o2 = po(db, s, "PO-2026-102", invoice_id=vpa.id)
    o3 = po(db, s, "PO-2026-103", invoice_id=vo.id)
    po(db, s, "PO-2026-104", invoice_id=vp.id)
    result = hub(db, s.W1, invoice_filter="outstanding_payment")
    # Then 1
    assert idset(result) == {o1.id, o2.id, o3.id}


# =========================================================================== #
# summarize_by_purchase_order_ids — sums (R2) and refunded total (BUG-2641, owner OQ-38)
# =========================================================================== #


def _verified_lines(db, s, o1):
    """The Given rows LA, LB, LC of OQ38-01 and OQ38-08."""
    line(
        db,
        s,
        o1,
        1,
        quantity_ordered=Decimal("10.00"),
        quantity_received=Decimal("7.00"),
        quantity_refunded=Decimal("3.00"),
    )
    line(db, s, o1, 2, item_id=s.IN1.id, quantity_ordered=Decimal("5.50"))
    line(db, s, o1, 3, item_id=s.IK.id, quantity_received=Decimal("1.00"))


# [claude] PUO-OQ38-01
def test_puo_oq38_01__verified_example(db, s):
    """PUO-OQ38-01 — the verified example: 3 lines, 16.50 ordered, 8.00 received, refunded not subtracted.
    Rules: summarize_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101", **stage(s.SR1))
    _verified_lines(db, s, o1)
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert set(result.keys()) == {o1.id}
    # Then 2
    assert result[o1.id]["item_count"] == 3
    # Then 3
    assert result[o1.id]["quantity_ordered_total"] == Decimal("16.50")
    # Then 4
    assert result[o1.id]["quantity_received_total"] == Decimal("8.00")


# [claude] PUO-OQ38-02
def test_puo_oq38_02__returned_plays_no_part(db, s):
    """PUO-OQ38-02 — a returned quantity plays no part.
    Rules: summarize_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(
        db,
        s,
        o1,
        1,
        quantity_ordered=Decimal("4.00"),
        quantity_received=Decimal("4.00"),
        quantity_returned=Decimal("2.00"),
    )
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["quantity_ordered_total"] == Decimal("4.00")
    # Then 2
    assert result[o1.id]["quantity_received_total"] == Decimal("4.00")


# [claude] PUO-OQ38-03
def test_puo_oq38_03__units_added_together(db, s):
    """PUO-OQ38-03 — quantities of items in different units are added together.
    Rules: summarize_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1, quantity_ordered=Decimal("2.00"))
    line(
        db,
        s,
        o1,
        2,
        item_id=s.IK.id,
        quantity_ordered=Decimal("1.50"),
        quantity_received=Decimal("0.75"),
    )
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["quantity_ordered_total"] == Decimal("3.50")
    # Then 2
    assert result[o1.id]["quantity_received_total"] == Decimal("0.75")


# [claude] PUO-OQ38-04
def test_puo_oq38_04__exact_decimals(db, s):
    """PUO-OQ38-04 — sums are exact Decimals.
    Rules: summarize_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(
        db,
        s,
        o1,
        1,
        quantity_ordered=Decimal("0.10"),
        quantity_received=Decimal("0.05"),
    )
    line(
        db,
        s,
        o1,
        2,
        quantity_ordered=Decimal("0.20"),
        quantity_received=Decimal("0.05"),
    )
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["quantity_ordered_total"] == Decimal("0.30")
    # Then 2
    assert isinstance(result[o1.id]["quantity_ordered_total"], Decimal)
    # Then 3
    assert result[o1.id]["quantity_received_total"] == Decimal("0.10")


# [claude] PUO-OQ38-05
def test_puo_oq38_05__rounded_half_up_before_sum(db, s):
    """PUO-OQ38-05 — stored quantities are rounded half up before they are summed.
    Rules: summarize_by_purchase_order_ids R2; Model facts (quantity_ordered Numeric(15, 2)); HR-15."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1, quantity_ordered=Decimal("2.125"))
    line(db, s, o1, 2, quantity_ordered=Decimal("0.005"))
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["quantity_ordered_total"] == Decimal("2.14")


# [claude] PUO-OQ38-06
def test_puo_oq38_06__each_po_own_sums(db, s):
    """PUO-OQ38-06 — each asked PO gets its own sums.
    Rules: summarize_by_purchase_order_ids R1, R2."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102")
    o3 = po(db, s, "PO-2026-103")
    line(db, s, o1, 1, quantity_ordered=Decimal("2.00"))
    line(db, s, o2, 1, quantity_ordered=Decimal("50.00"))
    line(
        db,
        s,
        o3,
        1,
        quantity_ordered=Decimal("3.00"),
        quantity_received=Decimal("1.00"),
    )
    line(
        db,
        s,
        o1,
        2,
        quantity_ordered=Decimal("4.00"),
        quantity_received=Decimal("4.00"),
    )
    result = summarize(db, s.W1, [o3.id, o1.id])
    # Then 1
    assert set(result.keys()) == {o1.id, o3.id}
    # Then 2
    assert result[o1.id]["item_count"] == 2
    # Then 3
    assert result[o1.id]["quantity_ordered_total"] == Decimal("6.00")
    # Then 4
    assert result[o1.id]["quantity_received_total"] == Decimal("4.00")
    # Then 5
    assert result[o3.id]["item_count"] == 1
    # Then 6
    assert result[o3.id]["quantity_ordered_total"] == Decimal("3.00")
    # Then 7
    assert result[o3.id]["quantity_received_total"] == Decimal("1.00")


# [claude] PUO-OQ38-07
def test_puo_oq38_07__same_item_two_lines(db, s):
    """PUO-OQ38-07 — the same item on two lines counts as two lines.
    Rules: summarize_by_purchase_order_ids R2."""
    o1 = po(db, s, "PO-2026-101")
    line(db, s, o1, 1)
    line(db, s, o1, 2)
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["item_count"] == 2
    # Then 2
    assert result[o1.id]["quantity_ordered_total"] == Decimal("2.00")


# [claude] PUO-OQ38-08
@pytest.mark.xfail(strict=True, reason=B2641)
def test_puo_oq38_08__verified_example_refunded(db, s):
    """PUO-OQ38-08 — the verified example also carries 3.00 refunded.
    Rules: summarize_by_purchase_order_ids R2a [BUG-2641]."""
    o1 = po(db, s, "PO-2026-101", **stage(s.SR1))
    _verified_lines(db, s, o1)
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["quantity_ordered_total"] == Decimal("16.50")
    # Then 2
    assert result[o1.id]["quantity_received_total"] == Decimal("8.00")
    # Then 3
    assert result[o1.id]["quantity_refunded_total"] == Decimal("3.00")
    # Then 4
    assert set(result[o1.id].keys()) == {
        "item_count",
        "quantity_ordered_total",
        "quantity_received_total",
        "quantity_refunded_total",
    }


# [claude] PUO-OQ38-09
@pytest.mark.xfail(strict=True, reason=B2641)
def test_puo_oq38_09__nothing_refunded_zero(db, s):
    """PUO-OQ38-09 — nothing refunded gives 0, and a returned quantity is not refunded.
    Rules: summarize_by_purchase_order_ids R2a [BUG-2641]."""
    o1 = po(db, s, "PO-2026-101")
    line(
        db,
        s,
        o1,
        1,
        quantity_ordered=Decimal("4.00"),
        quantity_received=Decimal("4.00"),
        quantity_returned=Decimal("2.00"),
    )
    result = summarize(db, s.W1, [o1.id])
    # Then 1
    assert result[o1.id]["item_count"] == 1
    # Then 2
    assert result[o1.id]["quantity_refunded_total"] == 0
    # Then 3
    assert isinstance(result[o1.id]["quantity_refunded_total"], Decimal)


# [claude] PUO-OQ38-10
@pytest.mark.xfail(strict=True, reason=B2641)
def test_puo_oq38_10__refunded_per_order(db, s):
    """PUO-OQ38-10 — refunded totals are exact and kept per order.
    Rules: summarize_by_purchase_order_ids R1, R2a [BUG-2641]."""
    o1 = po(db, s, "PO-2026-101")
    o2 = po(db, s, "PO-2026-102")
    line(
        db,
        s,
        o1,
        1,
        quantity_ordered=Decimal("1.00"),
        quantity_refunded=Decimal("0.10"),
    )
    line(
        db,
        s,
        o2,
        1,
        quantity_ordered=Decimal("9.00"),
        quantity_refunded=Decimal("5.00"),
    )
    line(
        db,
        s,
        o1,
        2,
        quantity_ordered=Decimal("1.00"),
        quantity_refunded=Decimal("0.20"),
    )
    result = summarize(db, s.W1, [o1.id, o2.id])
    # Then 1
    assert set(result.keys()) == {o1.id, o2.id}
    # Then 2
    assert result[o1.id]["quantity_refunded_total"] == Decimal("0.30")
    # Then 3
    assert result[o2.id]["quantity_refunded_total"] == Decimal("5.00")
