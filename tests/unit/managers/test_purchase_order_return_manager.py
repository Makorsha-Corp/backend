"""Unit tests for app/managers/purchase_order_return_manager.py.

Implements tests/unit/managers/purchase_order_return_manager.cases.md
(revision 3, 2026-11-19), one test per case, in card order. Revision 3 added
the PORM-RR-* cards (`validate_replacement_receipt`, BUG-2810); the schema
`PurchaseOrderReturnReplacementCreate` is imported inside each RR test. Real Postgres
session (`db` fixture). Externals: none is mocked, no race simulations
(Conventions). The Q47 cards void the credit note through the real
`account_invoice_manager.void_invoice` (Conventions "Other manager").
The commit spy of PORM-S-14 wraps the real `db.commit`.

Twin: tests/unit/managers/test_sales_order_return_manager.py (same card
numbers, same helper names).

Built in normal mode (no local model): every test sits below a
`# [claude] <ID>` comment.
"""

# ruff: noqa: DTZ001, FURB157  (Conventions prescribe naive datetimes and Decimal("q") literals)
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.managers.account_invoice_manager import account_invoice_manager
from app.managers.purchase_order_return_manager import purchase_order_return_manager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.item import Item
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.status import Status
from app.schemas.purchase_order_return import (
    PurchaseOrderReturnCreate,
    PurchaseOrderReturnItemCreate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> actors and fixed values
# --------------------------------------------------------------------------- #

# Convention "RM" and "AIM" (module-level singletons, not fixtures)
RM = purchase_order_return_manager
AIM = account_invoice_manager

# Convention "MISSING"
MISSING = 999999999

# Convention "T1, T2, T3, T4" (naive)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)
T3 = datetime(2026, 3, 4, 11, 0)
T4 = datetime(2026, 3, 4, 12, 0)

# xfail reasons: bug titles from docs/testing/bugs.md
X2429 = "BUG-2429: an order's returns of one creation time come back in no fixed order"
X2750 = "BUG-2750: a completed return's quantity is taken off twice from what can still be returned"
X2751 = (
    "BUG-2751: one order line sent twice in a return is checked line by line, "
    "so more than was received can be returned"
)
X2752 = "BUG-2752: return quantities and prices with more than 2 decimals are accepted"
X2753 = "BUG-2753: two returns started at once can together reserve more than was received"
X2754 = "BUG-2754: return read before complete / void is not locked"
X2755 = "BUG-2755: a return's lines in the response have no sort order"
X2785 = "BUG-2785: a purchase return's unit price can be negative or above what was paid"
X2787 = "BUG-2787: returning an unpriced purchase line makes a 0.00 credit line"
X2788 = "BUG-2788: voiding a return credit note leaves its return untouched"
X2792 = "BUG-2792: another workspace's pending return lines reserve quantity on a line"
X2810 = (
    "BUG-2810: replacement goods for a `replace` return on a completed PO can't be received: "
    "a completed PO refuses receiving"
)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def s(db):
    """Convention "Standing rows" 1-4 and TAG. `s.W1`, `s.O2`, `s.I1`, `s.AC1`, ..."""
    r = SimpleNamespace()
    r.TAG = uuid.uuid4().hex[:8]
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2 = make_profile(db), make_profile(db)
    for suffix, ws in (("0", r.W0), ("1", r.W1), ("9", r.W2)):
        setattr(r, "F" + suffix, _add(db, Factory(workspace_id=ws.id, name="Store", abbreviation="ST")))
        setattr(r, "ST" + suffix, _add(db, Status(workspace_id=ws.id, name="Receiving", comment="stage")))
        setattr(r, "AC" + suffix, _add(db, Account(workspace_id=ws.id, name="Supplier")))
    r.I1 = _add(db, Item(workspace_id=r.W1.id, name="Pump", name_normalized="pump", unit="pcs"))
    r.I2 = _add(db, Item(workspace_id=r.W1.id, name="Valve", name_normalized="valve", unit="pcs"))
    for name, ws, factory, st in (
        ("O0", r.W0, r.F0, r.ST0),
        ("O1", r.W1, r.F1, r.ST1),
        ("O2", r.W1, r.F1, r.ST1),
        ("O3", r.W1, r.F1, r.ST1),
        ("O9", r.W2, r.F9, r.ST9),
    ):
        setattr(
            r,
            name,
            _add(
                db,
                PurchaseOrder(
                    workspace_id=ws.id,
                    po_number=f"PO-{r.TAG}-{name}",
                    destination_type="storage",
                    destination_id=factory.id,
                    current_status_id=st.id,
                    created_by=r.U1.id,
                ),
            ),
        )
    r.AC_OF = {r.W0.id: r.AC0, r.W1.id: r.AC1, r.W2.id: r.AC9}
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def mk_line(db, s, k, **cols):
    """Convention "line k" (line 2 always has `item_id I2.id`); `cols` = the columns after "but"."""
    fields = {
        "workspace_id": s.W1.id,
        "purchase_order_id": s.O2.id,
        "line_number": k,
        "item_id": s.I2.id if k == 2 else s.I1.id,
        "quantity_ordered": Decimal("10.00"),
        "quantity_received": Decimal("10.00"),
        "quantity_returned": Decimal("0.00"),
        "quantity_refunded": Decimal("0.00"),
        "unit_price": Decimal("10.00"),
    }
    fields.update(cols)
    return _add(db, PurchaseOrderItem(**fields))


def mk_return(db, s, n, **cols):
    """Convention "return N"; `status` and `paid` left to their defaults unless "but" sets them."""
    fields = {
        "workspace_id": s.W1.id,
        "purchase_order_id": s.O2.id,
        "return_number": f"PR-{s.TAG}-{n}",
        "return_type": "refund",
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, PurchaseOrderReturn(**fields))


def completed(s):
    """Convention "completed" (on a return)."""
    return {"status": "completed", "completed_at": T4, "completed_by": s.U1.id}


# Convention "voided" (on a return)
VOIDED = {"status": "voided", "paid": False, "updated_at": T4}


def mk_rline(db, ret, line, q, **cols):
    """Convention "rline of R on L, q"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": ret.workspace_id,
        "return_id": ret.id,
        "po_item_id": line.id,
        "item_id": line.item_id,
        "quantity_returned": Decimal(q),
        "unit_price": Decimal("10.00"),
    }
    fields.update(cols)
    return _add(db, PurchaseOrderReturnItem(**fields))


def mk_cn(db, s, ws, payment_status, **cols):
    """Convention "credit note of W, s"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": ws.id,
        "account_id": s.AC_OF[ws.id].id,
        "invoice_type": "receivable",
        "invoice_amount": Decimal("40.00"),
        "invoice_date": date(2026, 3, 4),
        "payment_status": payment_status,
    }
    fields.update(cols)
    return _add(db, AccountInvoice(**fields))


def voided_cn(db, s):
    """Convention "voided credit note"."""
    return mk_cn(db, s, s.W1, "unpaid", invoice_status="voided")


def confirmed_cn(db, s, **cols):
    """Convention "confirmed credit note"; `cols` = the columns after "but"."""
    fields = {"payment_status": "unpaid", "invoice_status": "confirmed"}
    fields.update(cols)
    payment_status = fields.pop("payment_status")
    return mk_cn(db, s, s.W1, payment_status, **fields)


def void_step(db, s, cn):
    """Convention "void step" of the Q47 cards, run exactly as written."""
    AIM.void_invoice(db, invoice_id=cn.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    db.expire_all()


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def bump_l(db, x):
    """Convention "bumpL(X)"."""
    db.execute(
        text("UPDATE purchase_order_return_items SET notes = notes WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


# --------------------------------------------------------------------------- #
# Conventions -> Requests
# --------------------------------------------------------------------------- #


def LN(line, q, **kw):
    """Convention "LN(L, "q")" (and `notes=n`). No `unit_price` unless the card writes one."""
    return PurchaseOrderReturnItemCreate(po_item_id=line.id, quantity_returned=Decimal(q), **kw)


def REQ(*items):
    """Convention "REQ(a, b, ...)"."""
    return PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=list(items))


def V(db, s, req):
    """Convention "V(req)"."""
    return RM.validate_and_build_items(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id, data=req)


def TOO(q, n, a):
    """Convention "TOO(q, n, a)" (the dash is U+2014)."""
    return f"Cannot return {q} of line {n} — only {a} available to return"


def NOTHERE(i):
    """Convention "NOTHERE(id)"."""
    return f"Item {i} does not belong to this purchase order"


# Conventions "Replacement receipts (RR cards)". The schema
# `PurchaseOrderReturnReplacementCreate` is imported inside each RR test and
# passed in as `cls`, so a missing class fails only that test.
def RRQ(cls, *pairs):
    """Convention "RRQ((X, "q"), ...)"; `MISSING` in place of X sends `return_item_id MISSING`."""
    return cls(
        items=[
            {"return_item_id": MISSING if x == MISSING else x.id, "quantity": Decimal(q)} for x, q in pairs
        ]
    )


def RV(db, s, ret, req):
    """Convention "RV(R, req)"."""
    return RM.validate_replacement_receipt(db, ret=ret, workspace_id=s.W1.id, data=req)


def RTOO(total, n, left):
    """Convention "RTOO(total, n, left)" (the dash is U+2014)."""
    return f"Cannot receive {total} replacement(s) for line {n} — only {left} still to replace"


def NOTPART(i, ret):
    """Convention "NOTPART(id, R)"."""
    return f"Line {i} is not part of return {ret.return_number}"


def replaced_l1(db, s):
    """Card shorthand "L1 = line 1, but `quantity_received 6.00`, `quantity_returned 4.00`"
    (4 sent back on a replace return, completed)."""
    return mk_line(db, s, 1, quantity_received=Decimal("6.00"), quantity_returned=Decimal("4.00"))


def replace_rc(db, s, n="001", **cols):
    """Card shorthand "RC = return "N", but `return_type "replace"`, completed"."""
    return mk_return(db, s, n, return_type="replace", **{**completed(s), **cols})


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #


def reread(db, model, row_id):
    """Convention "re-read X": expire, then SELECT X by id."""
    db.expire_all()
    return db.scalar(select(model).where(model.id == row_id))


def snap(db, model, row_id):
    """Convention "unchanged(X)": every column of the re-read row."""
    row = reread(db, model, row_id)
    return {c.key: getattr(row, c.key) for c in sa_inspect(model).mapper.column_attrs}


def counts(db):
    """Convention "nothing written": row counts of the four tables, all workspaces."""
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (PurchaseOrderReturn, PurchaseOrderReturnItem, PurchaseOrderItem, AccountInvoice)
    )


def assert_session_clean(db):
    """Convention "session clean": three asserts on `db`, before anything is re-read."""
    assert not db.new
    assert not db.dirty
    assert not db.deleted


class Recorder:
    """Convention "Statement recorder": the SQL the session's connection sends
    from `start()` (the start of the When) to the end of the test."""

    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []
        self.on = False

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def start(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        self.on = True
        return self

    def stop(self):
        if self.on:
            event.remove(self.bind, "before_cursor_execute", self._record)
            self.on = False

    @property
    def selects(self):
        return [st for st in self.statements if st.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [
            st for st in self.statements if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]

    def sel(self, table):
        """`sel(t)`: the SELECTs whose FROM names table `t`."""
        return [st for st in self.selects if table in _from_tables(st)]


_FROM_END = re.compile(r"\b(WHERE|ORDER BY|GROUP BY|LIMIT|OFFSET|FOR UPDATE|HAVING)\b")


def _from_tables(statement):
    """The table names in the FROM part of a SELECT (joins included)."""
    flat = " ".join(statement.split())
    if " FROM " not in flat:
        return set()
    from_part = flat.split(" FROM ", 1)[1]
    stop = _FROM_END.search(from_part)
    if stop:
        from_part = from_part[: stop.start()]
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", from_part))


def order_part(statement):
    """`order_part(s)`: the text of `s` after its first ORDER BY ("" if none)."""
    flat = " ".join(statement.split())
    return flat.split("ORDER BY", 1)[1] if "ORDER BY" in flat else ""


def no_lock(rec):
    """Convention "no lock"."""
    return all("FOR UPDATE" not in st for st in rec.selects)


def locks(rec, table):
    """Convention "locks t"."""
    return any(
        "FOR UPDATE" in st and "SKIP LOCKED" not in st and "NOWAIT" not in st for st in rec.sel(table)
    )


@pytest.fixture
def rec(db):
    """A statement recorder for the card; started by the test at its When."""
    r = Recorder(db)
    yield r
    r.stop()


# =========================================================================== #
# PurchaseOrderReturnManager.has_open_return
# =========================================================================== #


# [claude] PORM-HO-01
def test_porm_ho_01__one_pending_return_makes_order_open(db, s):
    """PORM-HO-01 — one pending return makes the order open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is True


# [claude] PORM-HO-02
def test_porm_ho_02__pending_among_completed_and_voided_counts(db, s):
    """PORM-HO-02 — a pending return among completed and voided ones still counts.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", **completed(s))
    mk_return(db, s, "002")
    mk_return(db, s, "003", **VOIDED)
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is True


# [claude] PORM-HO-03
def test_porm_ho_03__only_completed_and_voided_not_open(db, s):
    """PORM-HO-03 — only completed and voided returns: not open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", **completed(s))
    mk_return(db, s, "002", **VOIDED)
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-04
def test_porm_ho_04__no_returns_not_open(db, s):
    """PORM-HO-04 — an order with no returns is not open.
    Rules: has_open_return R1."""
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-05
def test_porm_ho_05__neighbour_orders_pending_do_not_count(db, s):
    """PORM-HO-05 — pending returns of the orders on both sides do not count.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", purchase_order_id=s.O1.id)
    mk_return(db, s, "003", purchase_order_id=s.O3.id)
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-06
def test_porm_ho_06__w0_and_w2_pending_on_same_order_do_not_count(db, s):
    """PORM-HO-06 — pending returns of W0 and W2 on the same order id do not count.
    Rules: has_open_return R2."""
    mk_return(db, s, "000", workspace_id=s.W0.id)
    mk_return(db, s, "009", workspace_id=s.W2.id)
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-07
def test_porm_ho_07__w1_pending_not_seen_from_w0(db, s):
    """PORM-HO-07 — a W1 pending return is not seen from W0.
    Rules: has_open_return R2."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W0.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-08
def test_porm_ho_08__check_writes_nothing_no_lock(db, s, rec):
    """PORM-HO-08 — the check writes nothing and takes no lock.
    Rules: has_open_return R3."""
    mk_return(db, s, "001")
    db.expunge_all()
    rec.start()
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert rec.written == []
    # Then 4
    assert no_lock(rec)


# [claude] PORM-HO-09
def test_porm_ho_09__unknown_order_not_open(db, s):
    """PORM-HO-09 — an unknown order is not open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, purchase_order_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-HO-10
def test_porm_ho_10__w1_pending_not_seen_from_w2(db, s):
    """PORM-HO-10 — a W1 pending return is not seen from W2.
    Rules: has_open_return R2."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W2.id)
    # Then 1
    assert result is False


# =========================================================================== #
# PurchaseOrderReturnManager.validate_and_build_items
# =========================================================================== #


# [claude] PORM-V-01
def test_porm_v_01__one_line_takes_order_line_price(db, s):
    """PORM-V-01 — one line with no price sent takes the order line's price.
    Rules: validate_and_build_items R1, R7 (priced line), R8, Returns."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "4")))
    # Then 1
    assert result == [
        {
            "po_item_id": L1.id,
            "item_id": s.I1.id,
            "quantity_returned": Decimal("4"),
            "unit_price": Decimal("10.00"),
            "notes": None,
        }
    ]
    # Then 2
    assert type(result) is list
    assert type(result[0]) is dict
    # Then 3
    assert set(result[0].keys()) == {"po_item_id", "item_id", "quantity_returned", "unit_price", "notes"}


# [claude] PORM-V-02
def test_porm_v_02__two_lines_in_request_order_with_notes(db, s):
    """PORM-V-02 — two lines come back in request order with their notes as sent.
    Rules: validate_and_build_items R1, R8."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2, unit_price=Decimal("4.00"))
    db.expire_all()
    result = V(db, s, REQ(LN(L2, "3", notes="box dented"), LN(L1, "2", notes="")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0] == {
        "po_item_id": L2.id,
        "item_id": s.I2.id,
        "quantity_returned": Decimal("3"),
        "unit_price": Decimal("4.00"),
        "notes": "box dented",
    }
    # Then 3
    assert result[1] == {
        "po_item_id": L1.id,
        "item_id": s.I1.id,
        "quantity_returned": Decimal("2"),
        "unit_price": Decimal("10.00"),
        "notes": "",
    }


# [claude] PORM-V-03
def test_porm_v_03__exactly_received_accepted(db, s):
    """PORM-V-03 — exactly the received quantity is accepted.
    Rules: validate_and_build_items R3 (equal side), R4."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-04
def test_porm_v_04__one_hundredth_over_refused(db, s):
    """PORM-V-04 — one hundredth more than received is refused.
    Rules: validate_and_build_items R3 (over side); Errors row 2."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    before_l1 = snap(db, PurchaseOrderItem, L1.id)
    req = REQ(LN(L1, "10.01"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("10.01", 1, "10.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, PurchaseOrderItem, L1.id) == before_l1


# [claude] PORM-V-05
def test_porm_v_05__refused_quantity_printed_as_sent(db, s):
    """PORM-V-05 — the refused quantity is printed as sent.
    Rules: validate_and_build_items R3."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    req = REQ(LN(L1, "11"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot return 11 of line 1 — only 10.00 available to return"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-V-06
def test_porm_v_06__message_names_own_line_number(db, s):
    """PORM-V-06 — the message names the order line's own line number.
    Rules: validate_and_build_items R3 (D1)."""
    mk_line(db, s, 1)
    L3 = mk_line(db, s, 3, quantity_received=Decimal("2.00"))
    db.expire_all()
    req = REQ(LN(L3, "3"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot return 3 of line 3 — only 2.00 available to return"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-07
def test_porm_v_07__pending_reserves_rest_accepted(db, s):
    """PORM-V-07 — a pending return reserves its quantity: the rest is accepted.
    Rules: validate_and_build_items R4 (pending)."""
    L1 = mk_line(db, s, 1)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] PORM-V-08
def test_porm_v_08__pending_reserves_one_more_refused(db, s):
    """PORM-V-08 — a pending return reserves its quantity: one more is refused.
    Rules: validate_and_build_items R3, R4 (pending)."""
    L1 = mk_line(db, s, 1)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "4.00")
    db.expire_all()
    before = counts(db)
    req = REQ(LN(L1, "7"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", 1, "6.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-V-09
def test_porm_v_09__voided_reserves_nothing(db, s):
    """PORM-V-09 — a voided return reserves nothing.
    Rules: validate_and_build_items R4 (voided)."""
    L1 = mk_line(db, s, 1)
    RV = mk_return(db, s, "001", **VOIDED)
    mk_rline(db, RV, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-10
def test_porm_v_10__two_pending_add_up_rest_accepted(db, s):
    """PORM-V-10 — two pending returns add up: exactly the rest is accepted.
    Rules: validate_and_build_items R4 (sum of pending)."""
    L1 = mk_line(db, s, 1)
    RA = mk_return(db, s, "001")
    mk_rline(db, RA, L1, "4.00")
    RB = mk_return(db, s, "002")
    mk_rline(db, RB, L1, "3.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "3")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("3")


# [claude] PORM-V-11
def test_porm_v_11__two_pending_add_up_one_more_refused(db, s):
    """PORM-V-11 — two pending returns add up: one more is refused.
    Rules: validate_and_build_items R3, R4 (sum of pending)."""
    L1 = mk_line(db, s, 1)
    RA = mk_return(db, s, "001")
    mk_rline(db, RA, L1, "4.00")
    RB = mk_return(db, s, "002")
    mk_rline(db, RB, L1, "3.00")
    db.expire_all()
    req = REQ(LN(L1, "4"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("4", 1, "3.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-12
def test_porm_v_12__pending_on_other_line_does_not_reserve(db, s):
    """PORM-V-12 — a pending return on another line does not reserve this line.
    Rules: validate_and_build_items R4 (per line)."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L2, "9.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["po_item_id"] == L1.id


# [claude] PORM-V-13
def test_porm_v_13__refunded_quantity_does_not_lower_returnable(db, s):
    """PORM-V-13 — refunded quantity on the line does not lower what can be returned today.
    Rules: validate_and_build_items R4 (refunded quantity is not counted on its own)."""
    L1 = mk_line(db, s, 1, quantity_ordered=Decimal("12.00"), quantity_refunded=Decimal("2.00"))
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-14
@pytest.mark.xfail(strict=True, reason=X2750)
def test_porm_v_14__after_completed_return_held_quantity_returnable(db, s):
    """PORM-V-14 — after a completed return, what is still held can be returned.
    Rules: validate_and_build_items R4 [BUG-2750]."""
    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] PORM-V-15
@pytest.mark.xfail(strict=True, reason=X2750)
def test_porm_v_15__after_completed_return_one_more_refused_with_held(db, s):
    """PORM-V-15 — after a completed return, one more than is held is refused with the held quantity.
    Rules: validate_and_build_items R3, R4 [BUG-2750]."""
    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = REQ(LN(L1, "7"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", 1, "6.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-16
def test_porm_v_16__after_completed_more_than_held_refused(db, s):
    """PORM-V-16 — after a completed return, more than is held is refused (today and after the fix).
    Rules: validate_and_build_items R3, R4."""
    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    before_l1 = snap(db, PurchaseOrderItem, L1.id)
    req = REQ(LN(L1, "7"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail.startswith("Cannot return 7 of line 1 — only ")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, PurchaseOrderItem, L1.id) == before_l1


# [claude] PORM-V-17
@pytest.mark.xfail(strict=True, reason=X2750)
def test_porm_v_17__completed_replace_counted_once(db, s):
    """PORM-V-17 — a completed replace return (no refund) is counted once.
    Rules: validate_and_build_items R4 [BUG-2750]."""
    L1 = mk_line(db, s, 1, quantity_received=Decimal("6.00"), quantity_returned=Decimal("4.00"))
    RC = mk_return(db, s, "001", return_type="replace", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] PORM-V-18
@pytest.mark.xfail(strict=True, reason=X2750)
def test_porm_v_18__completed_and_pending_pending_alone_reserves(db, s):
    """PORM-V-18 — completed and pending together: the pending one alone reserves.
    Rules: validate_and_build_items R4 [BUG-2750]."""
    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    RP = mk_return(db, s, "002")
    mk_rline(db, RP, L1, "3.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "3")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("3")


# [claude] PORM-V-19
def test_porm_v_19__completed_and_pending_more_than_rest_refused(db, s):
    """PORM-V-19 — completed and pending together: more than the rest is refused (today and after).
    Rules: validate_and_build_items R3, R4."""
    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    RP = mk_return(db, s, "002")
    mk_rline(db, RP, L1, "3.00")
    db.expire_all()
    req = REQ(LN(L1, "4"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail.startswith("Cannot return 4 of line 1 — only ")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-20
@pytest.mark.xfail(strict=True, reason=X2750)
def test_porm_v_20__replace_completed_and_rereceived_all_returnable(db, s):
    """PORM-V-20 — a replace return completed and re-received: all ten can be returned.
    Rules: validate_and_build_items R4 [BUG-2750] (spec Q1 example)."""
    L1 = mk_line(db, s, 1, quantity_received=Decimal("10.00"), quantity_returned=Decimal("4.00"))
    RC = mk_return(db, s, "001", return_type="replace", **completed(s))
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-21
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_21__same_line_twice_added_up_refused(db, s):
    """PORM-V-21 — the same line sent twice is added up and refused over the limit.
    Rules: validate_and_build_items R5 [BUG-2751]; Errors row 2."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    req = REQ(LN(L1, "6"), LN(L1, "6"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", 1, "10.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-V-22
def test_porm_v_22__repeats_that_fit_stay_separate(db, s):
    """PORM-V-22 — repeats that fit stay separate lines, each with its own note.
    Rules: validate_and_build_items R5 (fits), R1, R8."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "6", notes="a"), LN(L1, "4", notes="b")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0] == {
        "po_item_id": L1.id,
        "item_id": s.I1.id,
        "quantity_returned": Decimal("6"),
        "unit_price": Decimal("10.00"),
        "notes": "a",
    }
    # Then 3
    assert result[1] == {
        "po_item_id": L1.id,
        "item_id": s.I1.id,
        "quantity_returned": Decimal("4"),
        "unit_price": Decimal("10.00"),
        "notes": "b",
    }


# [claude] PORM-V-23
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_23__three_repeats_added_up(db, s):
    """PORM-V-23 — three repeats are added up.
    Rules: validate_and_build_items R5 [BUG-2751]."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(LN(L1, "6"), LN(L1, "4"), LN(L1, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-24
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_24__repeats_split_by_other_line_added_up(db, s):
    """PORM-V-24 — repeats split by another line are still added up.
    Rules: validate_and_build_items R5 [BUG-2751]."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2)
    db.expire_all()
    req = REQ(LN(L1, "6"), LN(L2, "1"), LN(L1, "6"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-25
def test_porm_v_25__repeats_on_pending_fit_rest_exactly(db, s):
    """PORM-V-25 — repeats on top of a pending reservation fit the rest exactly.
    Rules: validate_and_build_items R4, R5 (fits)."""
    L1 = mk_line(db, s, 1)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "3"), LN(L1, "3")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [d["quantity_returned"] for d in result] == [Decimal("3"), Decimal("3")]


# [claude] PORM-V-26
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_26__repeats_on_pending_checked_against_rest(db, s):
    """PORM-V-26 — repeats on top of a pending reservation are checked against the rest.
    Rules: validate_and_build_items R4, R5 [BUG-2751]."""
    L1 = mk_line(db, s, 1)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "4.00")
    db.expire_all()
    req = REQ(LN(L1, "4"), LN(L1, "3"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", 1, "6.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-27
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_27__decimal_repeats_added_up_exactly(db, s):
    """PORM-V-27 — decimal repeats are added up exactly.
    Rules: validate_and_build_items R5 [BUG-2751]."""
    L1 = mk_line(db, s, 1, quantity_ordered=Decimal("1.00"), quantity_received=Decimal("1.00"))
    db.expire_all()
    req = REQ(LN(L1, "0.6"), LN(L1, "0.5"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("1.1", 1, "1.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-28
def test_porm_v_28__good_line_before_bad_does_not_help(db, s):
    """PORM-V-28 — a good line before a bad one does not help.
    Rules: validate_and_build_items R1, R2."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    req = REQ(LN(L1, "2"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1")))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-V-29
def test_porm_v_29__first_failing_line_wins_too_many_first(db, s):
    """PORM-V-29 — the first failing line in request order decides the error (too many first).
    Rules: validate_and_build_items R1."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(LN(L1, "11"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1")))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-30
def test_porm_v_30__first_failing_line_wins_not_on_order_first(db, s):
    """PORM-V-30 — the first failing line in request order decides the error (not on the order first).
    Rules: validate_and_build_items R1."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1")), LN(L1, "11"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-31
def test_porm_v_31__unknown_line_id_does_not_belong(db, s):
    """PORM-V-31 — an unknown line id does not belong.
    Rules: validate_and_build_items R2; Errors row 1."""
    mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    req = REQ(PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1")))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Item 999999999 does not belong to this purchase order"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-V-32
def test_porm_v_32__line_of_lower_id_order_does_not_belong(db, s):
    """PORM-V-32 — a line of the order with the lower id does not belong.
    Rules: validate_and_build_items R2."""
    mk_line(db, s, 1)
    LA = mk_line(db, s, 1, purchase_order_id=s.O1.id)
    db.expire_all()
    before_la = snap(db, PurchaseOrderItem, LA.id)
    req = REQ(LN(LA, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(LA.id)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, PurchaseOrderItem, LA.id) == before_la


# [claude] PORM-V-33
def test_porm_v_33__line_of_higher_id_order_does_not_belong(db, s):
    """PORM-V-33 — a line of the order with the higher id does not belong.
    Rules: validate_and_build_items R2."""
    mk_line(db, s, 1)
    LC = mk_line(db, s, 1, purchase_order_id=s.O3.id)
    db.expire_all()
    req = REQ(LN(LC, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(LC.id)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-34
def test_porm_v_34__w0_line_on_this_order_does_not_belong(db, s):
    """PORM-V-34 — a W0 line on this order id does not belong.
    Rules: validate_and_build_items R2 (HR-16)."""
    mk_line(db, s, 1)
    LZ = mk_line(db, s, 2, workspace_id=s.W0.id)
    db.expire_all()
    req = REQ(LN(LZ, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(LZ.id)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-35
def test_porm_v_35__w2_line_on_this_order_does_not_belong(db, s):
    """PORM-V-35 — a W2 line on this order id does not belong.
    Rules: validate_and_build_items R2 (HR-16)."""
    mk_line(db, s, 1)
    LN9 = mk_line(db, s, 2, workspace_id=s.W2.id)
    db.expire_all()
    req = REQ(LN(LN9, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(LN9.id)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-36
def test_porm_v_36__own_line_not_found_from_w2(db, s):
    """PORM-V-36 — W1's own line is not found when the caller's workspace is W2.
    Rules: validate_and_build_items R2 (workspace gate)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(LN(L1, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.validate_and_build_items(db, purchase_order_id=s.O2.id, workspace_id=s.W2.id, data=req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(L1.id)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-37
def test_porm_v_37__line_of_w2_order_does_not_belong(db, s):
    """PORM-V-37 — a line of a W2 order does not belong to a W1 order.
    Rules: validate_and_build_items R2 (HR-16: only the id sent is echoed)."""
    mk_line(db, s, 1)
    L9 = mk_line(db, s, 1, workspace_id=s.W2.id, purchase_order_id=s.O9.id)
    db.expire_all()
    req = REQ(LN(L9, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(L9.id)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-38
def test_porm_v_38__two_decimals_below_limit_kept_as_sent(db, s):
    """PORM-V-38 — two decimals below the limit are accepted and kept as sent.
    Rules: validate_and_build_items R3, R8."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "9.99")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("9.99")


# [claude] PORM-V-39
def test_porm_v_39__fractional_received_equal_accepted(db, s):
    """PORM-V-39 — a fractional received quantity: equal accepted.
    Rules: validate_and_build_items R3, R4 (stored values)."""
    L1 = mk_line(db, s, 1, quantity_ordered=Decimal("10.50"), quantity_received=Decimal("10.50"))
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10.50")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10.50")


# [claude] PORM-V-40
def test_porm_v_40__fractional_received_one_hundredth_more_refused(db, s):
    """PORM-V-40 — a fractional received quantity: one hundredth more refused.
    Rules: validate_and_build_items R3, R4 (stored values)."""
    L1 = mk_line(db, s, 1, quantity_ordered=Decimal("10.50"), quantity_received=Decimal("10.50"))
    db.expire_all()
    req = REQ(LN(L1, "10.51"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("10.51", 1, "10.50")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-41
def test_porm_v_41__fully_reserved_nothing_more(db, s):
    """PORM-V-41 — fully reserved by a pending return: nothing more can be returned.
    Rules: validate_and_build_items R3 (G1: `0` at zero), R4 (zero left)."""
    L1 = mk_line(db, s, 1)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "10.00")
    db.expire_all()
    req = REQ(LN(L1, "0.01"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot return 0.01 of line 1 — only 0 available to return"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-42
def test_porm_v_42__over_reserved_never_below_zero(db, s):
    """PORM-V-42 — over-reserved line (invalid state): available never goes below 0.
    Rules: validate_and_build_items R3 (G1: `0` below zero), R4 ("never below 0")."""
    L1 = mk_line(db, s, 1)
    RA = mk_return(db, s, "001")
    mk_rline(db, RA, L1, "6.00")
    mk_rline(db, RA, L1, "6.00")
    db.expire_all()
    req = REQ(LN(L1, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot return 1 of line 1 — only 0 available to return"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-43
def test_porm_v_43__passing_check_writes_nothing(db, s, rec):
    """PORM-V-43 — a passing check writes nothing and leaves the order lines as they were.
    Rules: validate_and_build_items R11."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2)
    RP = mk_return(db, s, "001")
    mk_rline(db, RP, L1, "4.00")
    db.expunge_all()
    before = counts(db)
    req = REQ(LN(L1, "6"), LN(L2, "10"))
    rec.start()
    result = V(db, s, req)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert rec.written == []
    # Then 4
    assert counts(db) == before
    # Then 5
    row1 = reread(db, PurchaseOrderItem, L1.id)
    assert row1.quantity_received == Decimal("10.00")
    assert row1.quantity_returned == Decimal("0.00")
    assert row1.quantity_refunded == Decimal("0.00")
    # Then 6
    row2 = reread(db, PurchaseOrderItem, L2.id)
    assert row2.quantity_received == Decimal("10.00")
    assert row2.quantity_returned == Decimal("0.00")
    assert row2.quantity_refunded == Decimal("0.00")


# [claude] PORM-V-44
@pytest.mark.xfail(strict=True, reason=X2753)
def test_porm_v_44__order_lines_read_with_row_lock(db, s, rec):
    """PORM-V-44 — the order's lines are read with a row lock before the check.
    Rules: validate_and_build_items R9 [BUG-2753] (HR-10)."""
    L1 = mk_line(db, s, 1)
    db.expunge_all()
    req = REQ(LN(L1, "4"))
    rec.start()
    result = V(db, s, req)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert locks(rec, "purchase_order_items") or locks(rec, "purchase_orders")
    # Then 3
    assert rec.written == []


# [claude] PORM-V-51
@pytest.mark.xfail(strict=True, reason=X2792)
def test_porm_v_51__w0_return_line_reserves_nothing(db, s):
    """PORM-V-51 — a W0 return line pointing at this line reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2792] (HR-16)."""
    L1 = mk_line(db, s, 1)
    R0 = mk_return(db, s, "000", workspace_id=s.W0.id)
    mk_rline(db, R0, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-52
@pytest.mark.xfail(strict=True, reason=X2792)
def test_porm_v_52__w2_return_line_reserves_nothing(db, s):
    """PORM-V-52 — a W2 return line pointing at this line reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2792] (HR-16)."""
    L1 = mk_line(db, s, 1)
    R9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    mk_rline(db, R9, L1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-53
@pytest.mark.xfail(strict=True, reason=X2792)
def test_porm_v_53__w2_return_line_on_w1_return_reserves_nothing(db, s):
    """PORM-V-53 — a return line of W2 on a W1 pending return reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2792] (both the line and its return must be of this workspace)."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    mk_rline(db, R, L1, "4.00", workspace_id=s.W2.id)
    db.expire_all()
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-V-54
def test_porm_v_54__unknown_line_between_repeats_wins(db, s):
    """PORM-V-54 — an unknown line between two repeats wins over the repeat that would go over.
    Rules: validate_and_build_items R1, R5 (running total: the first failing line in request order wins)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(
        LN(L1, "6"),
        PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("99")),
        LN(L1, "6"),
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-55
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_55__repeat_over_wins_over_later_unknown(db, s):
    """PORM-V-55 — a repeat that goes over wins over an unknown line after it.
    Rules: validate_and_build_items R1, R5 [BUG-2751] (running total)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(
        LN(L1, "6"),
        LN(L1, "6"),
        PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("99")),
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-V-56
@pytest.mark.xfail(strict=True, reason=X2751)
def test_porm_v_56__error_names_running_total(db, s):
    """PORM-V-56 — the error names the running total at the repeat that goes over, not the grand total.
    Rules: validate_and_build_items R5 [BUG-2751] (running total)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(LN(L1, "6"), LN(L1, "6"), LN(L1, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# =========================================================================== #
# Schemas PurchaseOrderReturnCreate / PurchaseOrderReturnItemCreate
# =========================================================================== #


# [claude] PORM-SCH-01
def test_porm_sch_01__empty_line_list_refused():
    """PORM-SCH-01 — an empty line list is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[])
    # Then 2
    assert "At least one item must be selected for return" in str(exc.value)


# [claude] PORM-SCH-02
def test_porm_sch_02__zero_quantity_refused():
    """PORM-SCH-02 — a zero quantity is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnCreate(
            return_type="refund",
            reason="Faulty",
            items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0"))],
        )
    # Then 2
    assert "All return quantities must be positive" in str(exc.value)


# [claude] PORM-SCH-03
def test_porm_sch_03__negative_quantity_refused():
    """PORM-SCH-03 — a negative quantity is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnCreate(
            return_type="refund",
            reason="Faulty",
            items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("-1"))],
        )
    # Then 2
    assert "All return quantities must be positive" in str(exc.value)


# [claude] PORM-SCH-04
def test_porm_sch_04__smallest_positive_quantity_passes():
    """PORM-SCH-04 — the smallest positive quantity passes.
    Rules: validate_and_build_items Inputs (other side of > 0), R10 (2 decimals allowed)."""
    result = PurchaseOrderReturnCreate(
        return_type="refund",
        reason="Faulty",
        items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0.01"))],
    )
    # Then 1
    assert result.items[0].quantity_returned == Decimal("0.01")
    # Then 2
    assert result.items[0].unit_price is None
    assert result.items[0].notes is None


# [claude] PORM-SCH-05
def test_porm_sch_05__other_return_type_refused():
    """PORM-SCH-05 — a return type other than replace / refund is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnCreate(
            return_type="exchange",
            reason="Faulty",
            items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))],
        )
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("return_type",)


# [claude] PORM-SCH-06
def test_porm_sch_06__return_type_compared_exactly():
    """PORM-SCH-06 — the return type is compared exactly (capital letter refused).
    Rules: validate_and_build_items Inputs."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnCreate(
            return_type="Refund",
            reason="Faulty",
            items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))],
        )
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("return_type",)


# [claude] PORM-SCH-07
def test_porm_sch_07__replace_passes():
    """PORM-SCH-07 — return type `replace` passes.
    Rules: validate_and_build_items Inputs."""
    result = PurchaseOrderReturnCreate(
        return_type="replace",
        reason="Faulty",
        items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))],
    )
    # Then 1
    assert result.return_type == "replace"


# [claude] PORM-SCH-15
def test_porm_sch_15__refund_passes():
    """PORM-SCH-15 — return type `refund` passes.
    Rules: validate_and_build_items Inputs."""
    result = PurchaseOrderReturnCreate(
        return_type="refund",
        reason="Faulty",
        items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))],
    )
    # Then 1
    assert result.return_type == "refund"


# [claude] PORM-SCH-08
@pytest.mark.xfail(strict=True, reason=X2752)
def test_porm_sch_08__quantity_three_decimals_refused():
    """PORM-SCH-08 — a quantity with 3 decimals is refused.
    Rules: validate_and_build_items R10 [BUG-2752]; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0.004"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] PORM-SCH-09
@pytest.mark.xfail(strict=True, reason=X2752)
def test_porm_sch_09__quantity_1_001_refused():
    """PORM-SCH-09 — a quantity of 1.001 is refused.
    Rules: validate_and_build_items R10 [BUG-2752]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1.001"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] PORM-SCH-10
@pytest.mark.xfail(strict=True, reason=X2752)
def test_porm_sch_10__price_three_decimals_refused():
    """PORM-SCH-10 — a price with 3 decimals is refused.
    Rules: validate_and_build_items R10 [BUG-2752]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("1.005"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] PORM-SCH-11
@pytest.mark.xfail(strict=True, reason=X2752)
def test_porm_sch_11__quantity_14_integer_digits_refused():
    """PORM-SCH-11 — a quantity with 14 integer digits is refused.
    Rules: validate_and_build_items R10 [BUG-2752]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("10000000000000"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] PORM-SCH-12
@pytest.mark.xfail(strict=True, reason=X2752)
def test_porm_sch_12__price_14_integer_digits_refused():
    """PORM-SCH-12 — a price with 14 integer digits is refused.
    Rules: validate_and_build_items R10 [BUG-2752]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(
            po_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("10000000000000")
        )
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] PORM-SCH-13
def test_porm_sch_13__13_digits_2_decimals_pass():
    """PORM-SCH-13 — 13 integer digits and 2 decimals pass in quantity and price.
    Rules: validate_and_build_items R10 (the valid side of both limits)."""
    result = PurchaseOrderReturnItemCreate(
        po_item_id=1,
        quantity_returned=Decimal("9999999999999.99"),
        unit_price=Decimal("9999999999999.99"),
    )
    # Then 1
    assert result.quantity_returned == Decimal("9999999999999.99")
    # Then 2
    assert result.unit_price == Decimal("9999999999999.99")


# [claude] PORM-SCH-14
def test_porm_sch_14__trailing_zero_decimals_pass():
    """PORM-SCH-14 — a whole quantity with trailing zero decimals passes.
    Rules: validate_and_build_items R10 (`"5.00"` has 2 decimals)."""
    result = PurchaseOrderReturnItemCreate(
        po_item_id=1, quantity_returned=Decimal("5.00"), unit_price=Decimal("2.50")
    )
    # Then 1
    assert result.quantity_returned == Decimal("5.00")
    # Then 2
    assert result.unit_price == Decimal("2.50")


# [claude] PORM-SCH-16
def test_porm_sch_16__only_return_type_and_items_required():
    """PORM-SCH-16 — only `return_type` and `items` are required on the return.
    Rules: validate_and_build_items Inputs (G2)."""
    result = PurchaseOrderReturnCreate(
        return_type="refund",
        items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))],
    )
    # Then 1
    assert result.reason is None
    # Then 2
    assert result.notes is None
    # Then 3
    assert len(result.items) == 1


# [claude] PORM-SCH-17
def test_porm_sch_17__line_without_quantity_refused():
    """PORM-SCH-17 — a line without a quantity is refused.
    Rules: validate_and_build_items Inputs (G2: line id and quantity required)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(po_item_id=1)
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] PORM-SCH-18
def test_porm_sch_18__line_without_order_line_id_refused():
    """PORM-SCH-18 — a line without the order line id is refused.
    Rules: validate_and_build_items Inputs (G2)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnItemCreate(quantity_returned=Decimal("1"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("po_item_id",)


# =========================================================================== #
# PurchaseOrderReturnManager.get_return
# =========================================================================== #


# [claude] PORM-G-01
def test_porm_g_01__pending_return_of_this_order_returned(db, s):
    """PORM-G-01 — a pending return of this order is returned.
    Rules: get_return R1."""
    R = mk_return(db, s, "001")
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, PurchaseOrderReturn)
    # Then 2
    assert result.id == R.id
    # Then 3
    assert result.status == "pending"


# [claude] PORM-G-02
def test_porm_g_02__completed_return_returned(db, s):
    """PORM-G-02 — a completed return is returned too.
    Rules: get_return R1 (any status)."""
    RC = mk_return(db, s, "001", **completed(s))
    result = RM.get_return(db, return_id=RC.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == RC.id
    # Then 2
    assert result.status == "completed"
    assert result.completed_by == s.U1.id


# [claude] PORM-G-03
def test_porm_g_03__unknown_id_404(db, s):
    """PORM-G-03 — an unknown id is 404.
    Rules: get_return R2; Errors row 1."""
    mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=MISSING, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Return with ID 999999999 not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-04
def test_porm_g_04__return_of_lower_id_order_404(db, s):
    """PORM-G-04 — a return of the lower-id order is 404 when asked under this order.
    Rules: get_return R2."""
    RA = mk_return(db, s, "001", purchase_order_id=s.O1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=RA.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {RA.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-05
def test_porm_g_05__return_of_higher_id_order_404(db, s):
    """PORM-G-05 — a return of the higher-id order is 404 when asked under this order.
    Rules: get_return R2."""
    RC3 = mk_return(db, s, "003", purchase_order_id=s.O3.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=RC3.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {RC3.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-06
def test_porm_g_06__w0_return_on_this_order_404(db, s):
    """PORM-G-06 — a W0 return on this order id is 404.
    Rules: get_return R2 (HR-16)."""
    R0 = mk_return(db, s, "000", workspace_id=s.W0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=R0.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {R0.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-07
def test_porm_g_07__w2_return_on_this_order_404(db, s):
    """PORM-G-07 — a W2 return on this order id is 404.
    Rules: get_return R2 (HR-16)."""
    R9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=R9.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {R9.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-08
def test_porm_g_08__w1_return_404_from_w0(db, s):
    """PORM-G-08 — a W1 return is 404 to a caller in W0.
    Rules: get_return R2 (workspace gate, lower side)."""
    R = mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {R.id} not found"


# [claude] PORM-G-09
def test_porm_g_09__default_read_writes_nothing_no_lock(db, s, rec):
    """PORM-G-09 — the default read writes nothing and takes no lock.
    Rules: get_return R3, R4 (default `False` reads without a lock)."""
    R = mk_return(db, s, "001")
    db.expunge_all()
    rec.start()
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == R.id
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert rec.written == []
    # Then 4
    assert no_lock(rec)


# [claude] PORM-G-10
@pytest.mark.xfail(strict=True, reason=X2754)
def test_porm_g_10__for_update_reads_with_lock(db, s, rec):
    """PORM-G-10 — `for_update=True` reads the return row with a lock.
    Rules: get_return R4 [BUG-2754] (HR-10)."""
    R = mk_return(db, s, "001")
    db.expunge_all()
    rec.start()
    result = RM.get_return(
        db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id, for_update=True
    )
    # Then 1
    assert result.id == R.id
    # Then 2
    assert result.status == "pending"
    # Then 3
    assert locks(rec, "purchase_order_returns")
    # Then 4
    assert rec.written == []


# [claude] PORM-G-11
@pytest.mark.xfail(strict=True, reason=X2754)
def test_porm_g_11__for_update_still_refuses_other_workspace(db, s):
    """PORM-G-11 — `for_update=True` still refuses a return of another workspace.
    Rules: get_return R2, R4 [BUG-2754]."""
    R9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(
            db, return_id=R9.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id, for_update=True
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {R9.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-G-12
@pytest.mark.xfail(strict=True, reason=X2754)
def test_porm_g_12__for_update_false_is_unlocked(db, s, rec):
    """PORM-G-12 — `for_update=False` is the unlocked read.
    Rules: get_return R4 [BUG-2754]."""
    R = mk_return(db, s, "001")
    db.expunge_all()
    rec.start()
    result = RM.get_return(
        db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id, for_update=False
    )
    # Then 1
    assert result.id == R.id
    # Then 2
    assert no_lock(rec)


# [claude] PORM-G-13
@pytest.mark.xfail(strict=True, reason=X2755)
def test_porm_g_13__lines_read_in_id_order(db, s, rec):
    """PORM-G-13 — the return's lines are read in id order.
    Rules: get_return R5 [BUG-2755] (HR-6)."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    A = mk_rline(db, R, L1, "1.00")
    B = mk_rline(db, R, L1, "2.00")
    db.expunge_all()
    rec.start()
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    lines = list(result.items)
    # Then 1
    assert sorted(x.id for x in lines) == [A.id, B.id]
    # Then 2
    assert any(
        "purchase_order_return_items.id" in order_part(st) for st in rec.sel("purchase_order_return_items")
    )


# [claude] PORM-G-14
@pytest.mark.xfail(strict=False, reason=X2755)
def test_porm_g_14__lines_in_id_order_after_update(db, s):
    """PORM-G-14 — the return's lines come back in id order after an update moves one.
    Rules: get_return R5 [BUG-2755]."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    A = mk_rline(db, R, L1, "1.00")
    B = mk_rline(db, R, L1, "2.00")
    C = mk_rline(db, R, L1, "3.00")
    seqscan(db)
    bump_l(db, A)
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [x.id for x in result.items] == [A.id, B.id, C.id]


# [claude] PORM-G-15
def test_porm_g_15__voided_return_returned(db, s):
    """PORM-G-15 — a voided return is returned too.
    Rules: get_return R1 (any status)."""
    RV = mk_return(db, s, "002", **VOIDED)
    result = RM.get_return(db, return_id=RV.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == RV.id
    # Then 2
    assert result.status == "voided"


# [claude] PORM-G-16
def test_porm_g_16__w1_return_404_from_w2(db, s):
    """PORM-G-16 — a W1 return is 404 to a caller in W2.
    Rules: get_return R2 (workspace gate, higher side)."""
    R = mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {R.id} not found"


# [claude] PORM-G-17
def test_porm_g_17__lines_are_exactly_its_own(db, s):
    """PORM-G-17 — the return's lines are exactly its own lines.
    Rules: get_return R1, R5 (the part that holds today: which lines, not their order)."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    A = mk_rline(db, R, L1, "1.00")
    B = mk_rline(db, R, L1, "2.00")
    R2 = mk_return(db, s, "002")
    mk_rline(db, R2, L1, "3.00")
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert sorted(x.id for x in result.items) == [A.id, B.id]
    # Then 2
    assert sorted(x.quantity_returned for x in result.items) == [Decimal("1.00"), Decimal("2.00")]


# =========================================================================== #
# PurchaseOrderReturnManager.list_returns
# =========================================================================== #


# [claude] PORM-L-01
def test_porm_l_01__returns_newest_first(db, s):
    """PORM-L-01 — the order's returns come newest first.
    Rules: list_returns R1."""
    RA = mk_return(db, s, "001", created_at=T1)
    RB = mk_return(db, s, "002", created_at=T3)
    RC = mk_return(db, s, "003", created_at=T2)
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RB.id, RC.id, RA.id]


# [claude] PORM-L-02
def test_porm_l_02__every_status_listed(db, s):
    """PORM-L-02 — every status is listed.
    Rules: list_returns R1."""
    RP = mk_return(db, s, "001", created_at=T1)
    RC = mk_return(db, s, "002", created_at=T2, **completed(s))
    RV = mk_return(db, s, "003", created_at=T3, **VOIDED)
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RV.id, RC.id, RP.id]
    # Then 2
    assert [r.status for r in result] == ["voided", "completed", "pending"]


# [claude] PORM-L-03
def test_porm_l_03__neighbour_orders_not_listed(db, s):
    """PORM-L-03 — returns of the orders on both sides are not listed.
    Rules: list_returns R1."""
    mk_return(db, s, "001", purchase_order_id=s.O1.id, created_at=T3)
    RB = mk_return(db, s, "002", created_at=T1)
    mk_return(db, s, "003", purchase_order_id=s.O3.id, created_at=T2)
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RB.id]


# [claude] PORM-L-04
def test_porm_l_04__w0_and_w2_returns_not_listed(db, s):
    """PORM-L-04 — W0 and W2 returns on this order id are not listed.
    Rules: list_returns R1 (HR-16)."""
    mk_return(db, s, "000", workspace_id=s.W0.id, created_at=T3)
    RB = mk_return(db, s, "002", created_at=T1)
    mk_return(db, s, "009", workspace_id=s.W2.id, created_at=T2)
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RB.id]


# [claude] PORM-L-05
def test_porm_l_05__unknown_order_empty_list(db, s):
    """PORM-L-05 — an unknown order gets an empty list.
    Rules: list_returns R1."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, purchase_order_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PORM-L-06
def test_porm_l_06__list_writes_nothing_no_lock(db, s, rec):
    """PORM-L-06 — the list writes nothing and takes no lock.
    Rules: list_returns R1 (Side effects: none)."""
    RB = mk_return(db, s, "002")
    db.expunge_all()
    rec.start()
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RB.id]
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert rec.written == []
    # Then 4
    assert no_lock(rec)


# [claude] PORM-L-07
@pytest.mark.xfail(strict=True, reason=X2429)
def test_porm_l_07__tie_broken_by_id_desc(db, s, rec):
    """PORM-L-07 — returns of one creation time are broken by id, newest first.
    Rules: list_returns R1 (DAO tie-break, BUG-2429)."""
    RA = mk_return(db, s, "001", created_at=T2)
    RB = mk_return(db, s, "002", created_at=T2)
    db.expunge_all()
    rec.start()
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert sorted(r.id for r in result) == [RA.id, RB.id]
    # Then 2
    assert any("purchase_order_returns.id DESC" in order_part(st) for st in rec.sel("purchase_order_returns"))


# [claude] PORM-L-08
@pytest.mark.xfail(strict=True, reason=X2755)
def test_porm_l_08__listed_lines_read_in_id_order(db, s, rec):
    """PORM-L-08 — each listed return's lines are read in id order.
    Rules: list_returns R2 [BUG-2755]."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    A = mk_rline(db, R, L1, "1.00")
    B = mk_rline(db, R, L1, "2.00")
    db.expunge_all()
    rec.start()
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    lines = list(result[0].items)
    # Then 1
    assert sorted(x.id for x in lines) == [A.id, B.id]
    # Then 2
    assert any(
        "purchase_order_return_items.id" in order_part(st) for st in rec.sel("purchase_order_return_items")
    )


# [claude] PORM-L-09
@pytest.mark.xfail(strict=False, reason=X2755)
def test_porm_l_09__listed_lines_in_id_order_after_update(db, s):
    """PORM-L-09 — listed lines come back in id order after an update moves one.
    Rules: list_returns R2 [BUG-2755]."""
    L1 = mk_line(db, s, 1)
    R = mk_return(db, s, "001")
    A = mk_rline(db, R, L1, "1.00")
    B = mk_rline(db, R, L1, "2.00")
    C = mk_rline(db, R, L1, "3.00")
    seqscan(db)
    bump_l(db, A)
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [x.id for x in result[0].items] == [A.id, B.id, C.id]


# [claude] PORM-L-10
def test_porm_l_10__w0_caller_sees_none(db, s):
    """PORM-L-10 — a caller in W0 sees none of W1's returns.
    Rules: list_returns R1 (workspace gate, lower side)."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W0.id)
    # Then 1
    assert result == []


# [claude] PORM-L-11
def test_porm_l_11__w2_caller_sees_none(db, s):
    """PORM-L-11 — a caller in W2 sees none of W1's returns.
    Rules: list_returns R1 (workspace gate, higher side)."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W2.id)
    # Then 1
    assert result == []


# [claude] PORM-L-12
def test_porm_l_12__each_return_carries_its_own_lines(db, s):
    """PORM-L-12 — each listed return carries exactly its own lines.
    Rules: list_returns R1, R2 (the part that holds today: which lines, not their order)."""
    L1 = mk_line(db, s, 1)
    RA = mk_return(db, s, "001", created_at=T1)
    A = mk_rline(db, RA, L1, "1.00")
    B = mk_rline(db, RA, L1, "2.00")
    RB = mk_return(db, s, "002", created_at=T2)
    C = mk_rline(db, RB, L1, "3.00")
    result = RM.list_returns(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [RB.id, RA.id]
    # Then 2
    assert sorted(x.id for x in result[0].items) == [C.id]
    # Then 3
    assert sorted(x.id for x in result[1].items) == [A.id, B.id]


# =========================================================================== #
# PurchaseOrderReturnManager.sync_return_paid
# (every card builds the return with `updated_at T1` and `updated_by None`)
# =========================================================================== #


# [claude] PORM-S-01
def test_porm_s_01__paid_credit_note_sets_paid(db, s):
    """PORM-S-01 — a fully paid credit note sets `paid` and reports the change.
    Rules: sync_return_paid R1, R5."""
    CN = mk_cn(db, s, s.W1, "paid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=False, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is True
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.updated_at != T1
    # Then 4
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "pending"
    assert row.updated_by is None
    assert row.completed_at is None
    assert row.completed_by is None
    assert row.invoice_id == CN.id
    # Then 5
    cn = reread(db, AccountInvoice, CN.id)
    assert cn.payment_status == "paid"


# [claude] PORM-S-02
def test_porm_s_02__partial_credit_note_clears_paid(db, s):
    """PORM-S-02 — a partly paid credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    CN = mk_cn(db, s, s.W1, "partial")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.updated_at != T1


# [claude] PORM-S-03
def test_porm_s_03__unpaid_credit_note_clears_paid(db, s):
    """PORM-S-03 — an unpaid credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    CN = mk_cn(db, s, s.W1, "unpaid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False


# [claude] PORM-S-04
def test_porm_s_04__overdue_credit_note_clears_paid(db, s):
    """PORM-S-04 — an overdue credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    CN = mk_cn(db, s, s.W1, "overdue")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False


# [claude] PORM-S-05
def test_porm_s_05__already_paid_still_paid_no_change(db, s, rec):
    """PORM-S-05 — already paid and still paid: no change, nothing flushed.
    Rules: sync_return_paid R4."""
    CN = mk_cn(db, s, s.W1, "paid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    rec.start()
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is False
    # Then 2
    assert R not in db.dirty
    # Then 3
    assert rec.written == []
    # Then 4
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is True
    assert row.updated_at == T1


# [claude] PORM-S-06
def test_porm_s_06__not_paid_still_not_paid_no_change(db, s, rec):
    """PORM-S-06 — not paid and still not paid: no change, nothing flushed.
    Rules: sync_return_paid R4."""
    CN = mk_cn(db, s, s.W1, "partial")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=False, updated_at=T1, updated_by=None)
    rec.start()
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is False
    # Then 2
    assert R not in db.dirty
    # Then 3
    assert rec.written == []
    # Then 4
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    assert row.updated_at == T1


# [claude] PORM-S-07
def test_porm_s_07__no_credit_note_clears_paid(db, s):
    """PORM-S-07 — no credit note: `paid` is cleared.
    Rules: sync_return_paid R3, R5."""
    R = mk_return(db, s, "001", invoice_id=None, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.updated_at != T1


# [claude] PORM-S-08
def test_porm_s_08__no_credit_note_not_paid_nothing_changes(db, s, rec):
    """PORM-S-08 — no credit note and not paid: nothing changes.
    Rules: sync_return_paid R3, R4."""
    R = mk_return(db, s, "001", invoice_id=None, paid=False, updated_at=T1, updated_by=None)
    rec.start()
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is False
    # Then 2
    assert rec.written == []
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    assert row.updated_at == T1


# [claude] PORM-S-09
def test_porm_s_09__w0_paid_invoice_does_not_count(db, s, rec):
    """PORM-S-09 — a paid invoice of W0 does not count as this return's credit note.
    Rules: sync_return_paid R1, R3 (HR-16, lower workspace id)."""
    C0 = mk_cn(db, s, s.W0, "paid")
    R = mk_return(db, s, "001", invoice_id=C0.id, paid=False, updated_at=T1, updated_by=None)
    before_c0 = snap(db, AccountInvoice, C0.id)
    R = reread(db, PurchaseOrderReturn, R.id)
    rec.start()
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is False
    # Then 2
    assert rec.written == []
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    assert row.updated_at == T1
    # Then 4
    assert snap(db, AccountInvoice, C0.id) == before_c0


# [claude] PORM-S-10
def test_porm_s_10__w2_paid_invoice_does_not_keep_paid(db, s):
    """PORM-S-10 — a paid invoice of W2 does not keep `paid` set.
    Rules: sync_return_paid R1, R3 (HR-16, higher workspace id)."""
    C9 = mk_cn(db, s, s.W2, "paid")
    R = mk_return(db, s, "001", invoice_id=C9.id, paid=True, updated_at=T1, updated_by=None)
    before_c9 = snap(db, AccountInvoice, C9.id)
    R = reread(db, PurchaseOrderReturn, R.id)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    # Then 3
    assert snap(db, AccountInvoice, C9.id) == before_c9


# [claude] PORM-S-11
def test_porm_s_11__voided_credit_note_clears_paid(db, s):
    """PORM-S-11 — a voided credit note clears `paid`.
    Rules: sync_return_paid R2 (owner freeze: a return credit note is voidable)."""
    CN = voided_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    # Then 3
    cn = reread(db, AccountInvoice, CN.id)
    assert cn.invoice_status == "voided"
    assert cn.payment_status == "unpaid"


# [claude] PORM-S-12
def test_porm_s_12__completed_return_follows_credit_note(db, s):
    """PORM-S-12 — a completed return follows its credit note too, and keeps its completion.
    Rules: sync_return_paid R1, R5 (any status; `completed_*` untouched)."""
    CN = mk_cn(db, s, s.W1, "paid")
    R = mk_return(
        db, s, "001", invoice_id=CN.id, paid=False, updated_at=T1, updated_by=None, **completed(s)
    )
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is True
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "completed"
    assert row.completed_at == T4
    assert row.completed_by == s.U1.id
    assert row.updated_by is None


# [claude] PORM-S-13
def test_porm_s_13__change_flushed_as_one_update(db, s, rec):
    """PORM-S-13 — a change is flushed in the call, as one UPDATE of the return.
    Rules: sync_return_paid R5 (flushed)."""
    CN = mk_cn(db, s, s.W1, "paid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=False, updated_at=T1, updated_by=None)
    rec.start()
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert R not in db.dirty
    # Then 3
    assert len(rec.written) == 1
    # Then 4
    assert rec.written[0].startswith("UPDATE purchase_order_returns")
    # Then 5
    assert no_lock(rec)


# [claude] PORM-S-14
def test_porm_s_14__change_not_committed(db, s):
    """PORM-S-14 — the change is not committed.
    Rules: sync_return_paid R5 (not committed)."""
    CN = mk_cn(db, s, s.W1, "paid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=False, updated_at=T1, updated_by=None)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
        # Then 1
        assert result is True
        # Then 2
        row = reread(db, PurchaseOrderReturn, R.id)
        assert row.paid is True
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    assert row.updated_at == T1


# =========================================================================== #
# PurchaseOrderReturnManager.validate_replacement_receipt — new method
# (BUG-2810, owner 2026-11-19). Every card is a strict xfail: neither the
# method nor PurchaseOrderReturnReplacementCreate exists yet. The schema is
# imported at the top of each test (Conventions), so today every RR test
# fails on that import, before `# Then 1`.
# =========================================================================== #


# [claude] PORM-RR-01
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_01__full_replacement_at_original_cost(db, s):
    """PORM-RR-01 — a full replacement of one line is accepted at the original line cost.
    Rules: validate_replacement_receipt RR5 (equal side), RR6, Returns."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "4")))
    # Then 1
    assert result == [
        {
            "return_item_id": A.id,
            "po_item_id": L1.id,
            "item_id": s.I1.id,
            "quantity": Decimal("4"),
            "unit_cost": Decimal("10.00"),
        }
    ]
    # Then 2
    assert type(result) is list
    assert type(result[0]) is dict


# [claude] PORM-RR-02
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_02__two_lines_in_request_order_own_cost(db, s):
    """PORM-RR-02 — two lines come back in request order, each at its own PO line cost.
    Rules: validate_replacement_receipt RR3, RR6, Returns."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    L2 = mk_line(
        db,
        s,
        2,
        unit_price=Decimal("4.00"),
        quantity_received=Decimal("8.00"),
        quantity_returned=Decimal("2.00"),
    )
    B = mk_rline(db, RC, L2, "2.00")
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (B, "1.5"), (A, "2")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0] == {
        "return_item_id": B.id,
        "po_item_id": L2.id,
        "item_id": s.I2.id,
        "quantity": Decimal("1.5"),
        "unit_cost": Decimal("4.00"),
    }
    # Then 3
    assert result[1] == {
        "return_item_id": A.id,
        "po_item_id": L1.id,
        "item_id": s.I1.id,
        "quantity": Decimal("2"),
        "unit_cost": Decimal("10.00"),
    }


# [claude] PORM-RR-03
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_03__one_hundredth_below_left_accepted(db, s):
    """PORM-RR-03 — one hundredth below what is left is accepted.
    Rules: validate_replacement_receipt RR5."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "3.99")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity"] == Decimal("3.99")


# [claude] PORM-RR-04
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_04__one_hundredth_over_returned_refused(db, s):
    """PORM-RR-04 — one hundredth over what was returned is refused.
    Rules: validate_replacement_receipt RR5; Errors row 4."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    before_a = snap(db, PurchaseOrderReturnItem, A.id)
    before_l1 = snap(db, PurchaseOrderItem, L1.id)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "4.01"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("4.01", 1, "4.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, PurchaseOrderReturnItem, A.id) == before_a
    # Then 6
    assert snap(db, PurchaseOrderItem, L1.id) == before_l1


# [claude] PORM-RR-05
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_05__already_replaced_lowers_limit_rest_accepted(db, s):
    """PORM-RR-05 — replacements already received lower the limit: the rest is accepted.
    Rules: validate_replacement_receipt RR5 (already replaced counts)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", quantity_replaced=Decimal("3.00"))
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "1")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity"] == Decimal("1")


# [claude] PORM-RR-06
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_06__already_replaced_lowers_limit_more_refused(db, s):
    """PORM-RR-06 — replacements already received lower the limit: more than the rest is refused.
    Rules: validate_replacement_receipt RR5 (already replaced counts); Errors row 4."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", quantity_replaced=Decimal("3.00"))
    db.expire_all()
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "2"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("2", 1, "1.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-RR-07
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_07__fully_replaced_nothing_left_printed_0(db, s):
    """PORM-RR-07 — a line fully replaced already: nothing is left, printed as 0.
    Rules: validate_replacement_receipt RR5 (`0` when nothing is left)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", quantity_replaced=Decimal("4.00"))
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "0.01"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("0.01", 1, "0")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-08
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_08__same_line_twice_running_total(db, s):
    """PORM-RR-08 — the same line twice is added up (running total).
    Rules: validate_replacement_receipt RR5 (running total)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "3"), (A, "2"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("5", 1, "4.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-09
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_09__running_total_plus_already_replaced(db, s):
    """PORM-RR-09 — the running total is added to what was already received.
    Rules: validate_replacement_receipt RR5 (running total + already replaced)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", quantity_replaced=Decimal("1.00"))
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "2"), (A, "2"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("4", 1, "3.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-10
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_10__repeats_that_fit_stay_separate(db, s):
    """PORM-RR-10 — repeats that fit stay separate entries.
    Rules: validate_replacement_receipt RR3, RR5 (fits)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "2"), (A, "2")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [d["quantity"] for d in result] == [Decimal("2"), Decimal("2")]
    # Then 3
    assert [d["return_item_id"] for d in result] == [A.id, A.id]


# [claude] PORM-RR-11
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_11__refund_return_cannot_receive(db, s):
    """PORM-RR-11 — a refund return cannot receive replacements.
    Rules: validate_replacement_receipt RR1; Errors row 1."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(
        db,
        s,
        1,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
        quantity_refunded=Decimal("4.00"),
    )
    RC = mk_return(db, s, "001", **completed(s))
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a replace return can receive replacements"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-RR-12
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_12__pending_replace_cannot_receive_yet(db, s):
    """PORM-RR-12 — a pending replace return cannot receive replacements yet.
    Rules: validate_replacement_receipt RR2; Errors row 2."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(db, s, 1)
    RC = mk_return(db, s, "001", return_type="replace")
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete the return before receiving replacements"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-RR-13
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_13__voided_replace_cannot_receive(db, s):
    """PORM-RR-13 — a voided replace return cannot receive replacements.
    Rules: validate_replacement_receipt RR2; Errors row 2."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(db, s, 1)
    RC = mk_return(db, s, "001", return_type="replace", **VOIDED)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete the return before receiving replacements"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-14
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_14__type_checked_before_status(db, s):
    """PORM-RR-14 — check order: the return type is checked before the status.
    Rules: validate_replacement_receipt RR1 before RR2."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(db, s, 1)
    RC = mk_return(db, s, "001")
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a replace return can receive replacements"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-15
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_15__status_checked_before_lines(db, s):
    """PORM-RR-15 — check order: the status is checked before the lines.
    Rules: validate_replacement_receipt RR2 before RR4, RR5."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(db, s, 1)
    RC = mk_return(db, s, "001", return_type="replace")
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (MISSING, "99"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete the return before receiving replacements"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-16
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_16__unknown_line_not_part(db, s):
    """PORM-RR-16 — an unknown line id is not part of the return.
    Rules: validate_replacement_receipt RR4; Errors row 3."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (MISSING, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(999999999, RC)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-RR-17
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_17__line_of_lower_id_return_not_part(db, s):
    """PORM-RR-17 — a line of a return with a lower id is not part of this return.
    Rules: validate_replacement_receipt RR4."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RA = replace_rc(db, s, "000")
    X = mk_rline(db, RA, L1, "1.00")
    RC = replace_rc(db, s, "001")
    mk_rline(db, RC, L1, "3.00")
    db.expire_all()
    before_x = snap(db, PurchaseOrderReturnItem, X.id)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (X, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(X.id, RC)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, PurchaseOrderReturnItem, X.id) == before_x


# [claude] PORM-RR-18
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_18__line_of_higher_id_return_not_part(db, s):
    """PORM-RR-18 — a line of a return with a higher id is not part of this return.
    Rules: validate_replacement_receipt RR4."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s, "001")
    mk_rline(db, RC, L1, "4.00")
    RB = replace_rc(db, s, "002")
    Y = mk_rline(db, RB, L1, "1.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (Y, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(Y.id, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-19
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_19__w0_line_on_this_return_not_part(db, s):
    """PORM-RR-19 — a W0 line on this return is not part of it.
    Rules: validate_replacement_receipt RR4 (HR-16)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    mk_rline(db, RC, L1, "4.00")
    Z = mk_rline(db, RC, L1, "1.00", workspace_id=s.W0.id)
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (Z, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(Z.id, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-20
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_20__w2_line_on_this_return_not_part(db, s):
    """PORM-RR-20 — a W2 line on this return is not part of it.
    Rules: validate_replacement_receipt RR4 (HR-16)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    mk_rline(db, RC, L1, "4.00")
    Z = mk_rline(db, RC, L1, "1.00", workspace_id=s.W2.id)
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (Z, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(Z.id, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-21
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_21__w0_caller_sees_no_lines(db, s):
    """PORM-RR-21 — a caller in W0 sees none of the return's lines.
    Rules: validate_replacement_receipt RR4 (workspace gate, lower side)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.validate_replacement_receipt(db, ret=RC, workspace_id=s.W0.id, data=req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(A.id, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-22
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_22__w2_caller_sees_no_lines(db, s):
    """PORM-RR-22 — a caller in W2 sees none of the return's lines.
    Rules: validate_replacement_receipt RR4 (workspace gate, higher side)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.validate_replacement_receipt(db, ret=RC, workspace_id=s.W2.id, data=req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(A.id, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-23
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_23__good_line_before_bad_does_not_help(db, s):
    """PORM-RR-23 — a good line before a bad one does not help.
    Rules: validate_replacement_receipt RR3, RR4."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "1"), (MISSING, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(999999999, RC)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-RR-24
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_24__first_failing_line_wins_too_many_first(db, s):
    """PORM-RR-24 — the first failing line in request order decides (too many first).
    Rules: validate_replacement_receipt RR3."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "5"), (MISSING, "1"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RTOO("5", 1, "4.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-25
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_25__not_part_first_then_repeat_over(db, s):
    """PORM-RR-25 — the first failing line in request order decides (not part first, then a repeat over).
    Rules: validate_replacement_receipt RR3, RR5 (running total in request order)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "3"), (MISSING, "1"), (A, "3"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RV(db, s, RC, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTPART(999999999, RC)
    # Then 3
    assert_session_clean(db)


# [claude] PORM-RR-26
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_26__unpriced_po_line_takes_return_line_price(db, s):
    """PORM-RR-26 — an unpriced PO line takes the return line's price as cost.
    Rules: validate_replacement_receipt RR6 (PO line price NULL)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = mk_line(
        db,
        s,
        1,
        unit_price=None,
        quantity_received=Decimal("6.00"),
        quantity_returned=Decimal("4.00"),
    )
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", unit_price=Decimal("7.50"))
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "2")))
    # Then 1
    assert result == [
        {
            "return_item_id": A.id,
            "po_item_id": L1.id,
            "item_id": s.I1.id,
            "quantity": Decimal("2"),
            "unit_cost": Decimal("7.50"),
        }
    ]


# [claude] PORM-RR-27
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_27__priced_po_line_cost_wins(db, s):
    """PORM-RR-27 — a priced PO line's cost wins over the return line's price.
    Rules: validate_replacement_receipt RR6 (original PO line cost)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00", unit_price=Decimal("7.50"))
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "2")))
    # Then 1
    assert result[0]["unit_cost"] == Decimal("10.00")


# [claude] PORM-RR-28
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_28__price_in_request_ignored(db, s):
    """PORM-RR-28 — a price sent in the request is ignored: there is no price field.
    Rules: validate_replacement_receipt RR6 (never the request's)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = RV(
        db,
        s,
        RC,
        PurchaseOrderReturnReplacementCreate(
            items=[{"return_item_id": A.id, "quantity": Decimal("1"), "unit_price": Decimal("1.00")}]
        ),
    )
    # Then 1
    assert result[0]["unit_cost"] == Decimal("10.00")
    # Then 2
    assert "unit_price" not in result[0]


# [claude] PORM-RR-29
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_29__completed_po_accepted(db, s):
    """PORM-RR-29 — a completed purchase order is accepted.
    Rules: validate_replacement_receipt RR7."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    STC = _add(db, Status(workspace_id=s.W1.id, name="Complete", comment="stage"))
    s.O2.current_status_id = STC.id
    db.flush()
    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expire_all()
    result = RV(db, s, RC, RRQ(PurchaseOrderReturnReplacementCreate, (A, "4")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity"] == Decimal("4")


# [claude] PORM-RR-30
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_30__passing_check_writes_nothing(db, s, rec):
    """PORM-RR-30 — a passing check writes nothing and leaves the return and the lines as they were.
    Rules: validate_replacement_receipt RR8."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    L1 = replaced_l1(db, s)
    RC = replace_rc(db, s)
    A = mk_rline(db, RC, L1, "4.00")
    db.expunge_all()
    RC = db.get(PurchaseOrderReturn, RC.id)
    before = counts(db)
    req = RRQ(PurchaseOrderReturnReplacementCreate, (A, "2"))
    rec.start()
    result = RV(db, s, RC, req)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert rec.written == []
    # Then 4
    assert counts(db) == before
    # Then 5
    row = reread(db, PurchaseOrderReturn, RC.id)
    assert row.status == "completed"
    assert row.return_type == "replace"
    assert row.completed_at == T4
    # Then 6
    a = reread(db, PurchaseOrderReturnItem, A.id)
    assert a.quantity_returned == Decimal("4.00")
    # Then 7
    l1 = reread(db, PurchaseOrderItem, L1.id)
    assert l1.quantity_received == Decimal("6.00")
    assert l1.quantity_returned == Decimal("4.00")
    assert l1.quantity_refunded == Decimal("0.00")


# [claude] PORM-RR-31
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_31__empty_receipt_refused():
    """PORM-RR-31 — an empty receipt is refused.
    Rules: PurchaseOrderReturnReplacementCreate (schema) Inputs."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnReplacementCreate(items=[])
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("items",)


# [claude] PORM-RR-32
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_32__zero_quantity_refused():
    """PORM-RR-32 — a zero quantity is refused.
    Rules: PurchaseOrderReturnReplacementCreate (schema) Inputs (> 0)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("0")}])
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("items", 0, "quantity")


# [claude] PORM-RR-33
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_33__three_decimals_refused():
    """PORM-RR-33 — a quantity with 3 decimals is refused.
    Rules: PurchaseOrderReturnReplacementCreate (schema) Inputs (2 decimals, as BUG-2752)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("0.004")}])
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("items", 0, "quantity")


# [claude] PORM-RR-34
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_34__fourteen_integer_digits_refused():
    """PORM-RR-34 — a quantity with 14 integer digits is refused.
    Rules: PurchaseOrderReturnReplacementCreate (schema) Inputs (13 integer digits)."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderReturnReplacementCreate(
            items=[{"return_item_id": 1, "quantity": Decimal("10000000000000")}]
        )
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("items", 0, "quantity")


# [claude] PORM-RR-35
@pytest.mark.xfail(strict=True, reason=X2810)
def test_porm_rr_35__valid_edges_pass():
    """PORM-RR-35 — the valid edges pass: 0.01 and 13 integer digits with 2 decimals, notes optional.
    Rules: PurchaseOrderReturnReplacementCreate (schema) Inputs."""
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    result = PurchaseOrderReturnReplacementCreate(
        items=[
            {"return_item_id": 1, "quantity": Decimal("0.01")},
            {"return_item_id": 2, "quantity": Decimal("9999999999999.99")},
        ]
    )
    # Then 1
    assert [i.quantity for i in result.items] == [Decimal("0.01"), Decimal("9999999999999.99")]
    # Then 2
    assert result.notes is None


# =========================================================================== #
# Return price range (validate_and_build_items R6, R6a) — BUG-2785, OQ-45
# =========================================================================== #


# [claude] PORM-Q45-01
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_01__negative_price_refused(db, s):
    """PORM-Q45-01 — a negative price is refused.
    Rules: validate_and_build_items R6 [BUG-2785]; Errors row 3."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    before = counts(db)
    req = REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("-5")))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 1 must be between 0 and 10.00"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-Q45-02
def test_porm_q45_02__price_zero_is_a_price(db, s):
    """PORM-Q45-02 — a price of 0 is a price, not "not sent", and is accepted.
    Rules: validate_and_build_items R6 (0 accepted)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("0"))),
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["unit_price"] == Decimal("0")
    # Then 3
    assert result[0]["unit_price"] is not None


# [claude] PORM-Q45-03
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_03__price_far_above_refused(db, s):
    """PORM-Q45-03 — a price far above the order line's price is refused.
    Rules: validate_and_build_items R6 [BUG-2785]."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999"))
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 1 must be between 0 and 10.00"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-04
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_04__one_hundredth_above_price_refused(db, s):
    """PORM-Q45-04 — one hundredth above the order line's price is refused.
    Rules: validate_and_build_items R6 [BUG-2785] (over side of the limit)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("10.01"))
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 1 must be between 0 and 10.00"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-05
def test_porm_q45_05__price_inside_range_used(db, s):
    """PORM-Q45-05 — a price inside the range is used instead of the line's.
    Rules: validate_and_build_items R6 (inside the range: used as sent), R8."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(
            PurchaseOrderReturnItemCreate(
                po_item_id=L1.id,
                quantity_returned=Decimal("2"),
                unit_price=Decimal("7.50"),
                notes="restocking fee",
            )
        ),
    )
    # Then 1
    assert result == [
        {
            "po_item_id": L1.id,
            "item_id": s.I1.id,
            "quantity_returned": Decimal("2"),
            "unit_price": Decimal("7.50"),
            "notes": "restocking fee",
        }
    ]


# [claude] PORM-Q45-06
def test_porm_q45_06__exactly_line_price_accepted(db, s):
    """PORM-Q45-06 — exactly the order line's price is accepted.
    Rules: validate_and_build_items R6 (equal side of the limit)."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(
            PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("10.00"))
        ),
    )
    # Then 1
    assert result[0]["unit_price"] == Decimal("10.00")


# [claude] PORM-Q45-07
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_07__unpriced_line_negative_price_refused(db, s):
    """PORM-Q45-07 — on an unpriced line a negative price is refused with its own text.
    Rules: validate_and_build_items R6 [BUG-2785] (unpriced line); Errors row 3."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("-1"))
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 1 cannot be negative"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-08
def test_porm_q45_08__unpriced_line_any_price_accepted(db, s):
    """PORM-Q45-08 — on an unpriced line any price >= 0 is accepted (no upper bound).
    Rules: validate_and_build_items R6 (unpriced line)."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(
            PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("99999"))
        ),
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["unit_price"] == Decimal("99999")


# [claude] PORM-Q45-09
def test_porm_q45_09__too_many_beats_bad_price(db, s):
    """PORM-Q45-09 — on one line, too many beats a bad price.
    Rules: validate_and_build_items R6a (quantity before price), R3."""
    L1 = mk_line(db, s, 1)
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("11"), unit_price=Decimal("99999"))
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-10
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_10__bad_price_first_beats_too_many_second(db, s):
    """PORM-Q45-10 — a bad price on the first line beats too many on the second.
    Rules: validate_and_build_items R1, R6a, R6 [BUG-2785]."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2)
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999")),
        LN(L2, "11"),
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 1 must be between 0 and 10.00"
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-11
def test_porm_q45_11__too_many_first_beats_bad_price_second(db, s):
    """PORM-Q45-11 — too many on the first line beats a bad price on the second.
    Rules: validate_and_build_items R1, R6a."""
    L1 = mk_line(db, s, 1)
    L2 = mk_line(db, s, 2)
    db.expire_all()
    req = REQ(
        LN(L1, "11"),
        PurchaseOrderReturnItemCreate(po_item_id=L2.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999")),
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q45-12
@pytest.mark.xfail(strict=True, reason=X2785)
def test_porm_q45_12__price_message_names_line_and_stored_price(db, s):
    """PORM-Q45-12 — the price message names the line's own number and its stored price.
    Rules: validate_and_build_items R6 [BUG-2785]; Errors row 3."""
    mk_line(db, s, 1)
    L3 = mk_line(db, s, 3, unit_price=Decimal("4.50"))
    db.expire_all()
    req = REQ(
        PurchaseOrderReturnItemCreate(po_item_id=L3.id, quantity_returned=Decimal("1"), unit_price=Decimal("4.51"))
    )
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return price for line 3 must be between 0 and 4.50"
    # Then 3
    assert_session_clean(db)


# =========================================================================== #
# Missing return price on an unpriced line (R7a, R6a) — BUG-2787, OQ-46
# =========================================================================== #


# [claude] PORM-Q46-01
@pytest.mark.xfail(strict=True, reason=X2787)
def test_porm_q46_01__unpriced_line_no_price_refused(db, s):
    """PORM-Q46-01 — an unpriced order line with no price sent is refused.
    Rules: validate_and_build_items R7a [BUG-2787]; Errors row 4."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    before = counts(db)
    req = REQ(LN(L1, "2"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Enter a return price for line 1 — the order line has no price"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] PORM-Q46-02
def test_porm_q46_02__unpriced_line_takes_sent_price(db, s):
    """PORM-Q46-02 — an unpriced order line with a price sent takes the sent price.
    Rules: validate_and_build_items R6, R7a (price sent)."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("4.00"))),
    )
    # Then 1
    assert result[0]["unit_price"] == Decimal("4.00")


# [claude] PORM-Q46-03
def test_porm_q46_03__unpriced_line_too_many_beats_missing_price(db, s):
    """PORM-Q46-03 — on an unpriced line, too many beats the missing price.
    Rules: validate_and_build_items R6a (quantity before missing price), R3."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    req = REQ(LN(L1, "11"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", 1, "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] PORM-Q46-04
def test_porm_q46_04__unpriced_line_zero_is_a_price(db, s):
    """PORM-Q46-04 — on an unpriced line a sent price of 0 is a price.
    Rules: validate_and_build_items R6, R7a (0 is a price)."""
    L1 = mk_line(db, s, 1, unit_price=None)
    db.expire_all()
    result = V(
        db,
        s,
        REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("0"))),
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["unit_price"] == Decimal("0")


# [claude] PORM-Q46-05
@pytest.mark.xfail(strict=True, reason=X2787)
def test_porm_q46_05__missing_price_first_beats_too_many_second(db, s):
    """PORM-Q46-05 — a missing price on the first line beats too many on the second.
    Rules: validate_and_build_items R1, R6a, R7a [BUG-2787]."""
    L1 = mk_line(db, s, 1, unit_price=None)
    L2 = mk_line(db, s, 2)
    db.expire_all()
    req = REQ(LN(L1, "2"), LN(L2, "11"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, req)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Enter a return price for line 1 — the order line has no price"
    # Then 3
    assert_session_clean(db)


# =========================================================================== #
# Credit-note void and the return (sync_return_paid R6) — BUG-2788, OQ-47
# =========================================================================== #


# [claude] PORM-Q47-01
def test_porm_q47_01__sync_on_pending_with_voided_cn_writes_only_paid(db, s):
    """PORM-Q47-01 — `sync_return_paid` on a pending return with a voided credit note writes only `paid`.
    Rules: sync_return_paid R5, R6 (this method writes only `paid`)."""
    CN = voided_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "pending"
    assert row.completed_at is None
    assert row.completed_by is None


# [claude] PORM-Q47-02
def test_porm_q47_02__sync_on_completed_with_voided_cn_writes_only_paid(db, s):
    """PORM-Q47-02 — `sync_return_paid` on a completed return with a voided credit note writes only `paid`.
    Rules: sync_return_paid R5, R6 (this method writes only `paid`)."""
    CN = voided_cn(db, s)
    R = mk_return(
        db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None, **completed(s)
    )
    result = RM.sync_return_paid(db, ret=R, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "completed"
    assert row.completed_at == T4


# [claude] PORM-Q47-03
@pytest.mark.xfail(strict=True, reason=X2788)
def test_porm_q47_03__after_void_pending_return_no_longer_open(db, s):
    """PORM-Q47-03 — after its credit note is voided, the pending return no longer keeps the order open.
    Rules: sync_return_paid R6 [BUG-2788]; has_open_return R1."""
    CN = confirmed_cn(db, s)
    mk_return(db, s, "001", invoice_id=CN.id)
    void_step(db, s, CN)
    result = RM.has_open_return(db, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] PORM-Q47-04
@pytest.mark.xfail(strict=True, reason=X2788)
def test_porm_q47_04__after_void_pending_return_no_longer_reserves(db, s):
    """PORM-Q47-04 — after its credit note is voided, the pending return no longer reserves its quantity.
    Rules: sync_return_paid R6 [BUG-2788]; validate_and_build_items R4."""
    L1 = mk_line(db, s, 1)
    CN = confirmed_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id)
    mk_rline(db, R, L1, "4.00")
    void_step(db, s, CN)
    result = V(db, s, REQ(LN(L1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] PORM-Q47-05
@pytest.mark.xfail(strict=True, reason=X2788)
def test_porm_q47_05__after_void_return_served_as_voided(db, s):
    """PORM-Q47-05 — after its credit note is voided, the return is served as voided (no longer completable).
    Rules: sync_return_paid R6 [BUG-2788]; get_return R1."""
    CN = confirmed_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id)
    void_step(db, s, CN)
    result = RM.get_return(db, return_id=R.id, purchase_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == R.id
    # Then 2
    assert result.status == "voided"
    # Then 3
    assert result.paid is False


# [claude] PORM-Q47-06
@pytest.mark.xfail(strict=True, reason=X2788)
def test_porm_q47_06__void_marks_pending_return_voided_unpaid(db, s):
    """PORM-Q47-06 — voiding a pending return's credit note marks the return voided, unpaid.
    Rules: sync_return_paid R6 [BUG-2788] (via void_invoice R3c)."""
    CN = confirmed_cn(db, s, payment_status="paid")
    R = mk_return(db, s, "001", invoice_id=CN.id, paid=True, updated_at=T1, updated_by=None)
    result = AIM.void_invoice(db, invoice_id=CN.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    # Then 1
    assert result.id == CN.id
    # Then 2
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "voided"
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.paid is False
    assert row.completed_at is None
    assert row.completed_by is None


# [claude] PORM-Q47-07
@pytest.mark.xfail(strict=True, reason=X2788)
def test_porm_q47_07__void_of_completed_returns_cn_refused(db, s):
    """PORM-Q47-07 — voiding a completed return's credit note is refused, nothing changes.
    Rules: sync_return_paid R6 [BUG-2788] (via void_invoice R3c)."""
    CN = confirmed_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id, updated_at=T1, updated_by=None, **completed(s))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AIM.void_invoice(db, invoice_id=CN.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == (
        "This return is completed — its goods have already moved. "
        "Start a new return or issue a separate credit note."
    )
    # Then 3
    assert_session_clean(db)
    # Then 4
    cn = reread(db, AccountInvoice, CN.id)
    assert cn.invoice_status == "confirmed"
    # Then 5
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "completed"
    assert row.completed_at == T4
    assert row.updated_at == T1


# [claude] PORM-Q47-08
def test_porm_q47_08__void_of_already_voided_returns_cn_leaves_return(db, s):
    """PORM-Q47-08 — voiding the credit note of an already voided return leaves the return as it is.
    Rules: sync_return_paid R6 (void_invoice R3c: already voided -> return unchanged)."""
    CN = confirmed_cn(db, s)
    R = mk_return(db, s, "001", invoice_id=CN.id, **VOIDED)
    result = AIM.void_invoice(db, invoice_id=CN.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    # Then 1
    assert result.id == CN.id
    # Then 2
    cn = reread(db, AccountInvoice, CN.id)
    assert cn.invoice_status == "voided"
    # Then 3
    row = reread(db, PurchaseOrderReturn, R.id)
    assert row.status == "voided"
    assert row.paid is False
    assert row.updated_at == T4
