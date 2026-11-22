# ruff: noqa: DTZ001, FURB157  (naive datetimes and Decimal("4") literals are prescribed by the cards)
"""Unit tests for app/managers/sales_order_return_manager.py.

Implements tests/unit/managers/sales_order_return_manager.cases.md (revision 2),
one test per case, in card order. Real Postgres session (`db` fixture).
Externals: none mocked, no race simulations (Conventions). The Q47 cards void
through the real `account_invoice_manager.void_invoice`; the commit spy of
SORM-S-14 wraps the real `db.commit`.

Twin of test_purchase_order_return_manager.py: same card numbers, same helper
names with sales models.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
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
from app.managers.sales_order_return_manager import sales_order_return_manager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.item import Item
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.status import Status
from app.schemas.sales_order_return import (
    SalesOrderReturnCreate,
    SalesOrderReturnItemCreate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> actors and fixed values
# --------------------------------------------------------------------------- #

RM = sales_order_return_manager  # Convention "RM"
AIM = account_invoice_manager  # Convention "Other manager: AIM"

MISSING = 999999999  # Convention "MISSING"

# Convention "T1, T2, T3, T4" (naive)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)
T3 = datetime(2026, 3, 4, 11, 0)
T4 = datetime(2026, 3, 4, 12, 0)

# Expect lines -> markers (reason: bug id and title from docs/testing/bugs.md)
X2423 = pytest.mark.xfail(strict=True, reason="BUG-2423: An order's returns of one creation time come back in no fixed order")
X2760 = pytest.mark.xfail(strict=True, reason="BUG-2760: A completed sales return's quantity is taken off twice from what can still be returned")
X2761 = pytest.mark.xfail(strict=True, reason="BUG-2761: One sales line sent twice in a return is checked line by line")
X2762 = pytest.mark.xfail(strict=True, reason="BUG-2762: Sales return quantities and prices with more than 2 decimals are accepted")
X2763 = pytest.mark.xfail(strict=True, reason="BUG-2763: Two sales returns started at once can together reserve more than was delivered")
X2764 = pytest.mark.xfail(strict=True, reason="BUG-2764: Sales return read before complete / void is not locked")
X2765 = pytest.mark.xfail(strict=True, reason="BUG-2765: A sales return's lines in the response have no sort order")
X2765_NS = pytest.mark.xfail(strict=False, reason="BUG-2765: A sales return's lines in the response have no sort order (non-strict: physical order)")
X2786 = pytest.mark.xfail(strict=True, reason="BUG-2786: A sales return's unit price can be negative or above the selling price")
X2788 = pytest.mark.xfail(strict=True, reason="BUG-2788: Voiding a return credit note leaves its return untouched")
X2796 = pytest.mark.xfail(strict=True, reason="BUG-2796: Another workspace's pending return lines reserve quantity on a sales line")
X2797 = pytest.mark.xfail(strict=True, reason='BUG-2797: The "too many" message shows the name of another workspace\'s item')


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    """Standing rows 1-4. `s.W1`, `s.O2`, `s.I1`, `s.AC1`, ...; `s.TAG` = TAG."""
    r = SimpleNamespace(TAG=uuid.uuid4().hex[:8])
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2 = make_profile(db), make_profile(db)
    for suffix, ws in (("0", r.W0), ("1", r.W1), ("9", r.W2)):
        setattr(r, "F" + suffix, _add(db, Factory(workspace_id=ws.id, name="Shop", abbreviation="SH")))
        setattr(r, "ST" + suffix, _add(db, Status(workspace_id=ws.id, name="Delivered", comment="stage")))
        setattr(r, "AC" + suffix, _add(db, Account(workspace_id=ws.id, name="Customer")))
    r.I1 = _add(db, Item(workspace_id=r.W1.id, name="Pump", name_normalized="pump", unit="pcs"))
    r.I2 = _add(db, Item(workspace_id=r.W1.id, name="Valve", name_normalized="valve", unit="pcs"))
    for name, ws, sfx in (("O0", r.W0, "0"), ("O1", r.W1, "1"), ("O2", r.W1, "1"), ("O3", r.W1, "1"), ("O9", r.W2, "9")):
        order = SalesOrder(
            workspace_id=ws.id,
            sales_order_number=f"SO-{r.TAG}-{name}",
            account_id=getattr(r, "AC" + sfx).id,
            factory_id=getattr(r, "F" + sfx).id,
            order_date=date(2026, 3, 1),
            total_amount=0,
            current_status_id=getattr(r, "ST" + sfx).id,
            created_by=r.U1.id,
        )
        setattr(r, name, _add(db, order))
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def mk_line(db, s, k=1, **cols):
    """Convention "line k" (line 2 has `item_id I2.id`); `cols` = the columns after "but"."""
    fields = {
        "workspace_id": s.W1.id,
        "sales_order_id": s.O2.id,
        "item_id": s.I2.id if k == 2 else s.I1.id,
        "description": None,
        "quantity_ordered": Decimal("10.00"),
        "quantity_delivered": Decimal("10.00"),
        "quantity_returned": Decimal("0.00"),
        "quantity_refunded": Decimal("0.00"),
        "unit_price": Decimal("10.00"),
        "line_total": Decimal("100.00"),
        "requires_delivery": True,
    }
    fields.update(cols)
    return _add(db, SalesOrderItem(**fields))


def mk_free(db, s, desc, **cols):
    """Convention "free line "D"" = line k, but `item_id None`, `description "D"`."""
    return mk_line(db, s, item_id=None, description=desc, **cols)


def mk_return(db, s, n, **cols):
    """Convention "return N"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": s.W1.id,
        "sales_order_id": s.O2.id,
        "return_number": f"SR-{s.TAG}-{n}",
        "return_type": "refund",
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, SalesOrderReturn(**fields))


def completed(s):
    """Convention "completed" (on a return)."""
    return {"status": "completed", "completed_at": T4, "completed_by": s.U1.id}


# Convention "voided" (on a return)
VOIDED = {"status": "voided", "paid": False, "updated_at": T4}


def mk_rline(db, ret, line, q, **cols):
    """Convention "rline of R on L, q"."""
    fields = {
        "workspace_id": ret.workspace_id,
        "return_id": ret.id,
        "so_item_id": line.id,
        "item_id": line.item_id,
        "quantity_returned": Decimal(q),
        "unit_price": Decimal("10.00"),
    }
    fields.update(cols)
    return _add(db, SalesOrderReturnItem(**fields))


def mk_cn(db, s, ws, pay_status, **cols):
    """Convention "credit note of W, s"."""
    ac = {s.W0.id: s.AC0, s.W1.id: s.AC1, s.W2.id: s.AC9}[ws.id]
    fields = {
        "workspace_id": ws.id,
        "account_id": ac.id,
        "invoice_type": "payable",
        "invoice_amount": Decimal("40.00"),
        "invoice_date": date(2026, 3, 4),
        "payment_status": pay_status,
    }
    fields.update(cols)
    return _add(db, AccountInvoice(**fields))


def voided_cn(db, s):
    """Convention "voided credit note"."""
    return mk_cn(db, s, s.W1, "unpaid", invoice_status="voided")


def confirmed_cn(db, s, **cols):
    """Convention "confirmed credit note"."""
    return mk_cn(db, s, s.W1, "unpaid", **{"invoice_status": "confirmed", **cols})


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def bump_l(db, x):
    """Convention "bumpL(X)"."""
    db.execute(text("UPDATE sales_order_return_items SET notes = notes WHERE id = :i"), {"i": x.id})
    db.expire_all()


def void_step(db, s, cn):
    """A Q47 "void step", exactly as written in the cards."""
    AIM.void_invoice(db, invoice_id=cn.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    db.expire_all()


# --------------------------------------------------------------------------- #
# Conventions -> requests
# --------------------------------------------------------------------------- #


def LN(line, q, **kw):
    """Convention "LN(L, "q")" (optionally `notes=`)."""
    return SalesOrderReturnItemCreate(so_item_id=line.id, quantity_returned=Decimal(q), **kw)


def REQ(*lines):
    """Convention "REQ(a, b, ...)"."""
    return SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=list(lines))


def V(db, s, req):
    """Convention "V(req)"."""
    return RM.validate_and_build_items(db, sales_order_id=s.O2.id, workspace_id=s.W1.id, data=req)


def TOO(q, name, a):
    """Convention "TOO(q, name, a)" (U+2014 dash)."""
    return f'Cannot return {q} of "{name}" — only {a} available to return'


def NOTHERE(i):
    """Convention "NOTHERE(id)"."""
    return f"Item {i} does not belong to this sales order"


def MISS(q="1"):
    """The cards' `SalesOrderReturnItemCreate(so_item_id=MISSING, quantity_returned=Decimal(q))`."""
    return SalesOrderReturnItemCreate(so_item_id=MISSING, quantity_returned=Decimal(q))


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def reread(db, model, row_id):
    """Convention "re-read X": expire, then SELECT X by id."""
    db.expire_all()
    return db.scalar(select(model).where(model.id == row_id))


def snap(db, model, row_id):
    """Convention "unchanged(X)": every column of the re-read row."""
    row = reread(db, model, row_id)
    return {c.key: getattr(row, c.key) for c in sa_inspect(model).mapper.column_attrs}


def totals(db):
    """Convention "nothing written": row counts of the four tables, all workspaces."""
    return tuple(
        db.scalar(select(func.count()).select_from(m))
        for m in (SalesOrderReturn, SalesOrderReturnItem, SalesOrderItem, AccountInvoice)
    )


def assert_session_clean(db):
    """Convention "session clean"."""
    assert not db.new
    assert not db.dirty
    assert not db.deleted


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
        return [st for st in self.statements if st.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [st for st in self.statements if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sel(self, table):
        """`sel(t)`: the SELECTs whose FROM names table t."""
        pattern = re.compile(rf"\b(?:FROM|JOIN)\s+{table}\b")
        return [st for st in self.selects if pattern.search(st)]

    def no_lock(self):
        """Convention "no lock"."""
        return all("FOR UPDATE" not in st for st in self.selects)

    def locks(self, table):
        """Convention "locks t"."""
        return any(
            "FOR UPDATE" in st and "SKIP LOCKED" not in st and "NOWAIT" not in st
            for st in self.sel(table)
        )


def order_part(st):
    """`order_part(s)`: the text after the first ORDER BY ("" if none)."""
    return st.split("ORDER BY", 1)[1] if "ORDER BY" in st else ""


# =========================================================================== #
# has_open_return
# =========================================================================== #


# [claude] SORM-HO-01
def test_sorm_ho_01__one_pending_return_opens_order(db, s):
    """SORM-HO-01 — one pending return makes the order open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is True


# [claude] SORM-HO-02
def test_sorm_ho_02__pending_among_completed_and_voided(db, s):
    """SORM-HO-02 — a pending return among completed and voided ones still counts.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", **completed(s))
    mk_return(db, s, "002")
    mk_return(db, s, "003", **VOIDED)
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is True


# [claude] SORM-HO-03
def test_sorm_ho_03__only_completed_and_voided_not_open(db, s):
    """SORM-HO-03 — only completed and voided returns: not open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", **completed(s))
    mk_return(db, s, "002", **VOIDED)
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-04
def test_sorm_ho_04__no_returns_not_open(db, s):
    """SORM-HO-04 — an order with no returns is not open.
    Rules: has_open_return R1."""
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-05
def test_sorm_ho_05__other_orders_pending_do_not_count(db, s):
    """SORM-HO-05 — pending returns of the orders on both sides do not count.
    Rules: has_open_return R1."""
    mk_return(db, s, "001", sales_order_id=s.O1.id)
    mk_return(db, s, "003", sales_order_id=s.O3.id)
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-06
def test_sorm_ho_06__w0_and_w2_pending_on_same_order_id(db, s):
    """SORM-HO-06 — pending returns of W0 and W2 on the same order id do not count.
    Rules: has_open_return R2."""
    mk_return(db, s, "000", workspace_id=s.W0.id)
    mk_return(db, s, "009", workspace_id=s.W2.id)
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-07
def test_sorm_ho_07__w1_pending_not_seen_from_w0(db, s):
    """SORM-HO-07 — a W1 pending return is not seen from W0.
    Rules: has_open_return R2."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W0.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-08
def test_sorm_ho_08__writes_nothing_takes_no_lock(db, s):
    """SORM-HO-08 — the check writes nothing and takes no lock.
    Rules: has_open_return R3."""
    mk_return(db, s, "001")
    o2, w1 = s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.has_open_return(db, sales_order_id=o2, workspace_id=w1)
        # Then 1
        assert result is True
        # Then 2
        assert_session_clean(db)
        # Then 3
        assert rec.written == []
        # Then 4
        assert rec.no_lock()


# [claude] SORM-HO-09
def test_sorm_ho_09__unknown_order_not_open(db, s):
    """SORM-HO-09 — an unknown order is not open.
    Rules: has_open_return R1."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, sales_order_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-HO-10
def test_sorm_ho_10__w1_pending_not_seen_from_w2(db, s):
    """SORM-HO-10 — a W1 pending return is not seen from W2.
    Rules: has_open_return R2."""
    mk_return(db, s, "001")
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W2.id)
    # Then 1
    assert result is False


# =========================================================================== #
# validate_and_build_items
# =========================================================================== #


# [claude] SORM-V-01
def test_sorm_v_01__no_price_sent_takes_line_price(db, s):
    """SORM-V-01 — one line with no price sent takes the order line's price.
    Rules: validate_and_build_items R1, R7 (priced line), R8, Returns."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "4")))
    # Then 1
    assert result == [{"so_item_id": l1.id, "item_id": s.I1.id, "quantity_returned": Decimal("4"), "unit_price": Decimal("10.00"), "notes": None}]
    # Then 2
    assert type(result) is list
    assert type(result[0]) is dict
    # Then 3
    assert set(result[0].keys()) == {"so_item_id", "item_id", "quantity_returned", "unit_price", "notes"}


# [claude] SORM-V-02
def test_sorm_v_02__two_lines_in_request_order_with_notes(db, s):
    """SORM-V-02 — two lines come back in request order with their notes as sent.
    Rules: validate_and_build_items R1, R8."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2, unit_price=Decimal("4.00"))
    db.expire_all()
    result = V(db, s, REQ(LN(l2, "3", notes="box dented"), LN(l1, "2", notes="")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0] == {"so_item_id": l2.id, "item_id": s.I2.id, "quantity_returned": Decimal("3"), "unit_price": Decimal("4.00"), "notes": "box dented"}
    # Then 3
    assert result[1] == {"so_item_id": l1.id, "item_id": s.I1.id, "quantity_returned": Decimal("2"), "unit_price": Decimal("10.00"), "notes": ""}


# [claude] SORM-V-03
def test_sorm_v_03__exactly_delivered_accepted(db, s):
    """SORM-V-03 — exactly the delivered quantity is accepted.
    Rules: validate_and_build_items R3 (equal side), R4."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-04
def test_sorm_v_04__one_hundredth_over_refused(db, s):
    """SORM-V-04 — one hundredth more than delivered is refused.
    Rules: validate_and_build_items R3 (over side); Errors row 2."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    before_l1 = snap(db, SalesOrderItem, l1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "10.01")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("10.01", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before
    # Then 5
    assert snap(db, SalesOrderItem, l1.id) == before_l1


# [claude] SORM-V-05
def test_sorm_v_05__refused_quantity_printed_as_sent(db, s):
    """SORM-V-05 — the refused quantity is printed as sent.
    Rules: validate_and_build_items R3."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 11 of "Pump" — only 10.00 available to return'
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-V-06
def test_sorm_v_06__free_text_line_named_by_description(db, s):
    """SORM-V-06 — a free-text line is named by its description.
    Rules: validate_and_build_items R3 (D1: catalog name, else description)."""
    mk_line(db, s, 1)
    lf = mk_free(db, s, "Install fee", quantity_delivered=Decimal("2.00"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lf, "3")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 3 of "Install fee" — only 2.00 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-07
def test_sorm_v_07__pending_reserves_rest_accepted(db, s):
    """SORM-V-07 — a pending return reserves its quantity: the rest is accepted.
    Rules: validate_and_build_items R4 (pending)."""
    l1 = mk_line(db, s, 1)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] SORM-V-08
def test_sorm_v_08__pending_reserves_one_more_refused(db, s):
    """SORM-V-08 — a pending return reserves its quantity: one more is refused.
    Rules: validate_and_build_items R3, R4 (pending)."""
    l1 = mk_line(db, s, 1)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "4.00")
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "7")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", "Pump", "6.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-V-09
def test_sorm_v_09__voided_reserves_nothing(db, s):
    """SORM-V-09 — a voided return reserves nothing.
    Rules: validate_and_build_items R4 (voided)."""
    l1 = mk_line(db, s, 1)
    rv = mk_return(db, s, "001", **VOIDED)
    mk_rline(db, rv, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-10
def test_sorm_v_10__two_pending_add_up_rest_accepted(db, s):
    """SORM-V-10 — two pending returns add up: exactly the rest is accepted.
    Rules: validate_and_build_items R4 (sum of pending)."""
    l1 = mk_line(db, s, 1)
    ra = mk_return(db, s, "001")
    mk_rline(db, ra, l1, "4.00")
    rb = mk_return(db, s, "002")
    mk_rline(db, rb, l1, "3.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "3")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("3")


# [claude] SORM-V-11
def test_sorm_v_11__two_pending_add_up_one_more_refused(db, s):
    """SORM-V-11 — two pending returns add up: one more is refused.
    Rules: validate_and_build_items R3, R4 (sum of pending)."""
    l1 = mk_line(db, s, 1)
    ra = mk_return(db, s, "001")
    mk_rline(db, ra, l1, "4.00")
    rb = mk_return(db, s, "002")
    mk_rline(db, rb, l1, "3.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "4")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("4", "Pump", "3.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-12
def test_sorm_v_12__pending_on_other_line_does_not_reserve(db, s):
    """SORM-V-12 — a pending return on another line does not reserve this line.
    Rules: validate_and_build_items R4 (per line)."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l2, "9.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["so_item_id"] == l1.id


# [claude] SORM-V-13
def test_sorm_v_13__refunded_quantity_not_counted(db, s):
    """SORM-V-13 — refunded quantity on the line does not lower what can be returned today.
    Rules: validate_and_build_items R4 (refunded quantity is not counted on its own)."""
    l1 = mk_line(db, s, 1, quantity_ordered=Decimal("12.00"), quantity_refunded=Decimal("2.00"))
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-14
@X2760
def test_sorm_v_14__after_completed_return_held_quantity_returnable(db, s):
    """SORM-V-14 — after a completed return, what is still held can be returned.
    Rules: validate_and_build_items R4 [BUG-2760]."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    rc = mk_return(db, s, "001", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] SORM-V-15
@X2760
def test_sorm_v_15__after_completed_return_over_refused_with_held(db, s):
    """SORM-V-15 — after a completed return, one more than is held is refused with the held quantity.
    Rules: validate_and_build_items R3, R4 [BUG-2760]."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    rc = mk_return(db, s, "001", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "7")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", "Pump", "6.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-16
def test_sorm_v_16__after_completed_return_more_than_held_refused(db, s):
    """SORM-V-16 — after a completed return, more than is held is refused (today and after the fix).
    Rules: validate_and_build_items R3, R4."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    rc = mk_return(db, s, "001", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    db.expire_all()
    before = totals(db)
    before_l1 = snap(db, SalesOrderItem, l1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "7")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail.startswith('Cannot return 7 of "Pump" — only ')
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before
    # Then 5
    assert snap(db, SalesOrderItem, l1.id) == before_l1


# [claude] SORM-V-17
@X2760
def test_sorm_v_17__completed_replace_return_counted_once(db, s):
    """SORM-V-17 — a completed replace return (no refund) is counted once.
    Rules: validate_and_build_items R4 [BUG-2760]."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"))
    rc = mk_return(db, s, "001", return_type="replace", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "6")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("6")


# [claude] SORM-V-18
@X2760
def test_sorm_v_18__completed_and_pending_only_pending_reserves(db, s):
    """SORM-V-18 — completed and pending together: the pending one alone reserves.
    Rules: validate_and_build_items R4 [BUG-2760]."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    rc = mk_return(db, s, "001", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    rp = mk_return(db, s, "002")
    mk_rline(db, rp, l1, "3.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "3")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("3")


# [claude] SORM-V-19
def test_sorm_v_19__completed_and_pending_more_than_rest_refused(db, s):
    """SORM-V-19 — completed and pending together: more than the rest is refused (today and after).
    Rules: validate_and_build_items R3, R4."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("6.00"), quantity_returned=Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    rc = mk_return(db, s, "001", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    rp = mk_return(db, s, "002")
    mk_rline(db, rp, l1, "3.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "4")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail.startswith('Cannot return 4 of "Pump" — only ')
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-20
@X2760
def test_sorm_v_20__replace_completed_and_redelivered_all_returnable(db, s):
    """SORM-V-20 — a replace return completed and redelivered: all ten can be returned.
    Rules: validate_and_build_items R4 [BUG-2760] (spec Q1 example)."""
    l1 = mk_line(db, s, 1, quantity_delivered=Decimal("10.00"), quantity_returned=Decimal("4.00"))
    rc = mk_return(db, s, "001", return_type="replace", **completed(s))
    mk_rline(db, rc, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-21
@X2761
def test_sorm_v_21__same_line_twice_added_up_refused(db, s):
    """SORM-V-21 — the same line sent twice is added up and refused over the limit.
    Rules: validate_and_build_items R5 [BUG-2761]; Errors row 2."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), LN(l1, "6")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-V-22
def test_sorm_v_22__repeats_that_fit_stay_separate(db, s):
    """SORM-V-22 — repeats that fit stay separate lines, each with its own note.
    Rules: validate_and_build_items R5 (fits), R1, R8."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "6", notes="a"), LN(l1, "4", notes="b")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0] == {"so_item_id": l1.id, "item_id": s.I1.id, "quantity_returned": Decimal("6"), "unit_price": Decimal("10.00"), "notes": "a"}
    # Then 3
    assert result[1] == {"so_item_id": l1.id, "item_id": s.I1.id, "quantity_returned": Decimal("4"), "unit_price": Decimal("10.00"), "notes": "b"}


# [claude] SORM-V-23
@X2761
def test_sorm_v_23__three_repeats_added_up(db, s):
    """SORM-V-23 — three repeats are added up.
    Rules: validate_and_build_items R5 [BUG-2761]."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), LN(l1, "4"), LN(l1, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-24
@X2761
def test_sorm_v_24__repeats_split_by_other_line_added_up(db, s):
    """SORM-V-24 — repeats split by another line are still added up.
    Rules: validate_and_build_items R5 [BUG-2761]."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), LN(l2, "1"), LN(l1, "6")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-25
def test_sorm_v_25__repeats_on_reservation_fit_exactly(db, s):
    """SORM-V-25 — repeats on top of a pending reservation fit the rest exactly.
    Rules: validate_and_build_items R4, R5 (fits)."""
    l1 = mk_line(db, s, 1)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "3"), LN(l1, "3")))
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [d["quantity_returned"] for d in result] == [Decimal("3"), Decimal("3")]


# [claude] SORM-V-26
@X2761
def test_sorm_v_26__repeats_on_reservation_checked_against_rest(db, s):
    """SORM-V-26 — repeats on top of a pending reservation are checked against the rest.
    Rules: validate_and_build_items R4, R5 [BUG-2761]."""
    l1 = mk_line(db, s, 1)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "4.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "4"), LN(l1, "3")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("7", "Pump", "6.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-27
@X2761
def test_sorm_v_27__decimal_repeats_added_up_exactly(db, s):
    """SORM-V-27 — decimal repeats are added up exactly.
    Rules: validate_and_build_items R5 [BUG-2761]."""
    l1 = mk_line(db, s, 1, quantity_ordered=Decimal("1.00"), quantity_delivered=Decimal("1.00"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "0.6"), LN(l1, "0.5")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("1.1", "Pump", "1.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-28
def test_sorm_v_28__good_line_before_bad_does_not_help(db, s):
    """SORM-V-28 — a good line before a bad one does not help.
    Rules: validate_and_build_items R1, R2."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "2"), MISS("1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-V-29
def test_sorm_v_29__first_failing_line_too_many_first(db, s):
    """SORM-V-29 — the first failing line in request order decides the error (too many first).
    Rules: validate_and_build_items R1."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "11"), MISS("1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-30
def test_sorm_v_30__first_failing_line_not_on_order_first(db, s):
    """SORM-V-30 — the first failing line in request order decides the error (not on the order first).
    Rules: validate_and_build_items R1."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(MISS("1"), LN(l1, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-31
def test_sorm_v_31__unknown_line_id_does_not_belong(db, s):
    """SORM-V-31 — an unknown line id does not belong.
    Rules: validate_and_build_items R2; Errors row 1."""
    mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(MISS("1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Item 999999999 does not belong to this sales order"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-V-32
def test_sorm_v_32__line_of_lower_order_does_not_belong(db, s):
    """SORM-V-32 — a line of the order with the lower id does not belong.
    Rules: validate_and_build_items R2."""
    mk_line(db, s, 1)
    la = mk_line(db, s, 1, sales_order_id=s.O1.id)
    db.expire_all()
    before_la = snap(db, SalesOrderItem, la.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(la, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(la.id)
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, SalesOrderItem, la.id) == before_la


# [claude] SORM-V-33
def test_sorm_v_33__line_of_higher_order_does_not_belong(db, s):
    """SORM-V-33 — a line of the order with the higher id does not belong.
    Rules: validate_and_build_items R2."""
    mk_line(db, s, 1)
    lc = mk_line(db, s, 1, sales_order_id=s.O3.id)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lc, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(lc.id)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-34
def test_sorm_v_34__w0_line_on_this_order_does_not_belong(db, s):
    """SORM-V-34 — a W0 line on this order id does not belong.
    Rules: validate_and_build_items R2 (HR-16)."""
    mk_line(db, s, 1)
    lz = mk_line(db, s, 2, workspace_id=s.W0.id)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lz, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(lz.id)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-35
def test_sorm_v_35__w2_line_on_this_order_does_not_belong(db, s):
    """SORM-V-35 — a W2 line on this order id does not belong.
    Rules: validate_and_build_items R2 (HR-16)."""
    mk_line(db, s, 1)
    ln9 = mk_line(db, s, 2, workspace_id=s.W2.id)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(ln9, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(ln9.id)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-36
def test_sorm_v_36__own_line_not_found_from_w2(db, s):
    """SORM-V-36 — W1's own line is not found when the caller's workspace is W2.
    Rules: validate_and_build_items R2 (workspace gate)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.validate_and_build_items(db, sales_order_id=s.O2.id, workspace_id=s.W2.id, data=REQ(LN(l1, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(l1.id)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-37
def test_sorm_v_37__line_of_w2_order_does_not_belong(db, s):
    """SORM-V-37 — a line of a W2 order does not belong to a W1 order.
    Rules: validate_and_build_items R2 (HR-16: only the id sent is echoed)."""
    mk_line(db, s, 1)
    l9 = mk_line(db, s, 1, workspace_id=s.W2.id, sales_order_id=s.O9.id)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l9, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(l9.id)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-38
def test_sorm_v_38__two_decimals_below_limit_kept(db, s):
    """SORM-V-38 — two decimals below the limit are accepted and kept as sent.
    Rules: validate_and_build_items R3, R8."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "9.99")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("9.99")


# [claude] SORM-V-39
def test_sorm_v_39__fractional_delivered_equal_accepted(db, s):
    """SORM-V-39 — a fractional delivered quantity: equal accepted.
    Rules: validate_and_build_items R3, R4 (stored values)."""
    l1 = mk_line(db, s, 1, quantity_ordered=Decimal("10.50"), quantity_delivered=Decimal("10.50"))
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10.50")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10.50")


# [claude] SORM-V-40
def test_sorm_v_40__fractional_delivered_one_hundredth_over_refused(db, s):
    """SORM-V-40 — a fractional delivered quantity: one hundredth more refused.
    Rules: validate_and_build_items R3, R4 (stored values)."""
    l1 = mk_line(db, s, 1, quantity_ordered=Decimal("10.50"), quantity_delivered=Decimal("10.50"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "10.51")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("10.51", "Pump", "10.50")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-41
def test_sorm_v_41__fully_reserved_nothing_more(db, s):
    """SORM-V-41 — fully reserved by a pending return: nothing more can be returned.
    Rules: validate_and_build_items R3 (G1: `0` at zero), R4 (zero left)."""
    l1 = mk_line(db, s, 1)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "10.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "0.01")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 0.01 of "Pump" — only 0 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-42
def test_sorm_v_42__over_reserved_never_below_zero(db, s):
    """SORM-V-42 — over-reserved line (invalid state): available never goes below 0.
    Rules: validate_and_build_items R3 (G1: `0` below zero), R4 ("never below 0")."""
    l1 = mk_line(db, s, 1)
    ra = mk_return(db, s, "001")
    mk_rline(db, ra, l1, "6.00")
    mk_rline(db, ra, l1, "6.00")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 1 of "Pump" — only 0 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-43
def test_sorm_v_43__passing_check_writes_nothing(db, s):
    """SORM-V-43 — a passing check writes nothing and leaves the order lines as they were.
    Rules: validate_and_build_items R11."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2)
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "4.00")
    l1_id, l2_id, o2, w1 = l1.id, l2.id, s.O2.id, s.W1.id
    db.expunge_all()
    before = totals(db)
    req = REQ(LN(l1, "6"), LN(l2, "10"))
    with StatementRecorder(db) as rec:
        result = RM.validate_and_build_items(db, sales_order_id=o2, workspace_id=w1, data=req)
        # Then 1
        assert len(result) == 2
        # Then 2
        assert_session_clean(db)
        # Then 3
        assert rec.written == []
        # Then 4
        assert totals(db) == before
        # Then 5
        r1 = reread(db, SalesOrderItem, l1_id)
        assert r1.quantity_delivered == Decimal("10.00")
        assert r1.quantity_returned == Decimal("0.00")
        assert r1.quantity_refunded == Decimal("0.00")
        # Then 6
        r2 = reread(db, SalesOrderItem, l2_id)
        assert r2.quantity_delivered == Decimal("10.00")
        assert r2.quantity_returned == Decimal("0.00")
        assert r2.quantity_refunded == Decimal("0.00")


# [claude] SORM-V-44
@X2763
def test_sorm_v_44__order_lines_read_with_row_lock(db, s):
    """SORM-V-44 — the order's lines are read with a row lock before the check.
    Rules: validate_and_build_items R9 [BUG-2763] (HR-10)."""
    l1 = mk_line(db, s, 1)
    o2, w1 = s.O2.id, s.W1.id
    db.expunge_all()
    req = REQ(LN(l1, "4"))
    with StatementRecorder(db) as rec:
        result = RM.validate_and_build_items(db, sales_order_id=o2, workspace_id=w1, data=req)
        # Then 1
        assert len(result) == 1
        # Then 2
        assert rec.locks("sales_order_items") or rec.locks("sales_orders")
        # Then 3
        assert rec.written == []


# [claude] SORM-V-46
def test_sorm_v_46__free_text_line_returnable(db, s):
    """SORM-V-46 — a free-text line can be returned: no catalog item, the line's price.
    Rules: validate_and_build_items R7, R8 (free-text line, `item_id None`)."""
    lf = mk_free(db, s, "Install fee", quantity_delivered=Decimal("5.00"), unit_price=Decimal("3.00"), line_total=Decimal("30.00"))
    db.expire_all()
    result = V(db, s, REQ(LN(lf, "2")))
    # Then 1
    assert result == [{"so_item_id": lf.id, "item_id": None, "quantity_returned": Decimal("2"), "unit_price": Decimal("3.00"), "notes": None}]


# [claude] SORM-V-47
def test_sorm_v_47__catalog_name_over_description(db, s):
    """SORM-V-47 — a catalog line that also has a description is named by the catalog item.
    Rules: validate_and_build_items R3 (D1: catalog name first)."""
    l1 = mk_line(db, s, 1, description="Blue pump, boxed")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 11 of "Pump" — only 10.00 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-48
def test_sorm_v_48__directly_fulfilled_counts_same_way(db, s):
    """SORM-V-48 — a directly fulfilled line counts its fulfilled quantity the same way.
    Rules: validate_and_build_items R4 (lines fulfilled directly)."""
    l1 = mk_line(db, s, 1, requires_delivery=False, quantity_delivered=Decimal("4.00"))
    rp = mk_return(db, s, "001")
    mk_rline(db, rp, l1, "1.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "3")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("3")


# [claude] SORM-V-49
def test_sorm_v_49__directly_fulfilled_one_more_refused(db, s):
    """SORM-V-49 — a directly fulfilled line: one more than fulfilled is refused.
    Rules: validate_and_build_items R3, R4 (lines fulfilled directly)."""
    l1 = mk_line(db, s, 1, requires_delivery=False, quantity_delivered=Decimal("4.00"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "5")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("5", "Pump", "4.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-50
@X2761
def test_sorm_v_50__free_text_line_twice_added_up(db, s):
    """SORM-V-50 — a free-text line sent twice is added up.
    Rules: validate_and_build_items R5 [BUG-2761] (spec Q2 example)."""
    lf = mk_free(db, s, "Install fee", quantity_delivered=Decimal("5.00"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lf, "5"), LN(lf, "5")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 10 of "Install fee" — only 5.00 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-51
@X2796
def test_sorm_v_51__w0_return_line_reserves_nothing(db, s):
    """SORM-V-51 — a W0 return line pointing at this line reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2796] (HR-16)."""
    l1 = mk_line(db, s, 1)
    r0 = mk_return(db, s, "000", workspace_id=s.W0.id)
    mk_rline(db, r0, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-52
@X2796
def test_sorm_v_52__w2_return_line_reserves_nothing(db, s):
    """SORM-V-52 — a W2 return line pointing at this line reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2796] (HR-16)."""
    l1 = mk_line(db, s, 1)
    r9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    mk_rline(db, r9, l1, "4.00")
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-53
@X2796
def test_sorm_v_53__w2_line_on_w1_return_reserves_nothing(db, s):
    """SORM-V-53 — a return line of W2 on a W1 pending return reserves nothing.
    Rules: validate_and_build_items R4a [BUG-2796] (both the line and its return must be of this workspace)."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    mk_rline(db, r, l1, "4.00", workspace_id=s.W2.id)
    db.expire_all()
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-V-54
def test_sorm_v_54__unknown_line_between_repeats_wins(db, s):
    """SORM-V-54 — an unknown line between two repeats wins over the repeat that would go over.
    Rules: validate_and_build_items R1, R5 (running total: the first failing line in request order wins)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), MISS("99"), LN(l1, "6")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NOTHERE(999999999)
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-55
@X2761
def test_sorm_v_55__repeat_over_wins_over_later_unknown_line(db, s):
    """SORM-V-55 — a repeat that goes over wins over an unknown line after it.
    Rules: validate_and_build_items R1, R5 [BUG-2761] (running total)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), LN(l1, "6"), MISS("99")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-56
@X2761
def test_sorm_v_56__error_names_running_total(db, s):
    """SORM-V-56 — the error names the running total at the repeat that goes over, not the grand total.
    Rules: validate_and_build_items R5 [BUG-2761] (running total)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "6"), LN(l1, "6"), LN(l1, "1")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("12", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-57
@X2797
def test_sorm_v_57__w2_item_not_named_description_used(db, s):
    """SORM-V-57 — a catalog item of W2 is not named: the line's description is used.
    Rules: validate_and_build_items R3a [BUG-2797] (HR-16)."""
    i9 = _add(db, Item(workspace_id=s.W2.id, name="Far Pump", name_normalized="far pump", unit="pcs"))
    lx = mk_line(db, s, 1, item_id=i9.id, description="Blue pump")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lx, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 11 of "Blue pump" — only 10.00 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-58
@X2797
def test_sorm_v_58__w0_item_no_description_named_by_id(db, s):
    """SORM-V-58 — a catalog item of W0 and no description: the line is named by the id sent.
    Rules: validate_and_build_items R3a [BUG-2797] (HR-16)."""
    i0 = _add(db, Item(workspace_id=s.W0.id, name="Zero Pump", name_normalized="zero pump", unit="pcs"))
    lx = mk_line(db, s, 1, item_id=i0.id)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lx, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f'Cannot return 11 of "Item {lx.id}" — only 10.00 available to return'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-59
def test_sorm_v_59__other_workspace_item_still_refused(db, s):
    """SORM-V-59 — today the name of the other workspace's item is refused all the same (400).
    Rules: validate_and_build_items R3 (the refusal itself holds today and after BUG-2797)."""
    i9 = _add(db, Item(workspace_id=s.W2.id, name="Far Pump", name_normalized="far pump", unit="pcs"))
    lx = mk_line(db, s, 1, item_id=i9.id, description="Blue pump")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lx, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail.startswith('Cannot return 11 of "')
    # Then 3
    assert_session_clean(db)


# [claude] SORM-V-60
def test_sorm_v_60__removed_item_of_this_workspace_keeps_name(db, s):
    """SORM-V-60 — a removed item of this workspace still gives its name.
    Rules: validate_and_build_items R3a (a removed item of this workspace keeps its name)."""
    ix = _add(db, Item(workspace_id=s.W1.id, name="Old Pump", name_normalized="old pump", unit="pcs", is_active=False))
    lx = mk_line(db, s, 1, item_id=ix.id, description="Blue pump")
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(lx, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Cannot return 11 of "Old Pump" — only 10.00 available to return'
    # Then 3
    assert_session_clean(db)


# =========================================================================== #
# Schemas SalesOrderReturnCreate / SalesOrderReturnItemCreate
# =========================================================================== #


def _one(q="1"):
    return [SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal(q))]


# [claude] SORM-SCH-01
def test_sorm_sch_01__empty_line_list_refused(s):
    """SORM-SCH-01 — an empty line list is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=[])
    # Then 2
    assert "At least one item must be selected for return" in str(exc.value)


# [claude] SORM-SCH-02
def test_sorm_sch_02__zero_quantity_refused(s):
    """SORM-SCH-02 — a zero quantity is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=_one("0"))
    # Then 2
    assert "All return quantities must be positive" in str(exc.value)


# [claude] SORM-SCH-03
def test_sorm_sch_03__negative_quantity_refused(s):
    """SORM-SCH-03 — a negative quantity is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=_one("-1"))
    # Then 2
    assert "All return quantities must be positive" in str(exc.value)


# [claude] SORM-SCH-04
def test_sorm_sch_04__smallest_positive_quantity_passes(s):
    """SORM-SCH-04 — the smallest positive quantity passes.
    Rules: validate_and_build_items Inputs (other side of > 0), R10 (2 decimals allowed)."""
    result = SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=_one("0.01"))
    # Then 1
    assert result.items[0].quantity_returned == Decimal("0.01")
    # Then 2
    assert result.items[0].unit_price is None
    assert result.items[0].notes is None


# [claude] SORM-SCH-05
def test_sorm_sch_05__other_return_type_refused(s):
    """SORM-SCH-05 — a return type other than replace / refund is refused.
    Rules: validate_and_build_items Inputs; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnCreate(return_type="exchange", reason="Faulty", items=_one())
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("return_type",)


# [claude] SORM-SCH-06
def test_sorm_sch_06__return_type_compared_exactly(s):
    """SORM-SCH-06 — the return type is compared exactly (capital letter refused).
    Rules: validate_and_build_items Inputs."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnCreate(return_type="Refund", reason="Faulty", items=_one())
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("return_type",)


# [claude] SORM-SCH-07
def test_sorm_sch_07__replace_passes(s):
    """SORM-SCH-07 — return type `replace` passes.
    Rules: validate_and_build_items Inputs."""
    result = SalesOrderReturnCreate(return_type="replace", reason="Faulty", items=_one())
    # Then 1
    assert result.return_type == "replace"


# [claude] SORM-SCH-15
def test_sorm_sch_15__refund_passes(s):
    """SORM-SCH-15 — return type `refund` passes.
    Rules: validate_and_build_items Inputs."""
    result = SalesOrderReturnCreate(return_type="refund", reason="Faulty", items=_one())
    # Then 1
    assert result.return_type == "refund"


# [claude] SORM-SCH-08
@X2762
def test_sorm_sch_08__quantity_three_decimals_refused(s):
    """SORM-SCH-08 — a quantity with 3 decimals is refused.
    Rules: validate_and_build_items R10 [BUG-2762]; Errors row 3."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("0.004"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] SORM-SCH-09
@X2762
def test_sorm_sch_09__quantity_1_001_refused(s):
    """SORM-SCH-09 — a quantity of 1.001 is refused.
    Rules: validate_and_build_items R10 [BUG-2762]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("1.001"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] SORM-SCH-10
@X2762
def test_sorm_sch_10__price_three_decimals_refused(s):
    """SORM-SCH-10 — a price with 3 decimals is refused.
    Rules: validate_and_build_items R10 [BUG-2762]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("1.005"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] SORM-SCH-11
@X2762
def test_sorm_sch_11__quantity_fourteen_integer_digits_refused(s):
    """SORM-SCH-11 — a quantity with 14 integer digits is refused.
    Rules: validate_and_build_items R10 [BUG-2762]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("10000000000000"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] SORM-SCH-12
@X2762
def test_sorm_sch_12__price_fourteen_integer_digits_refused(s):
    """SORM-SCH-12 — a price with 14 integer digits is refused.
    Rules: validate_and_build_items R10 [BUG-2762]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("10000000000000"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] SORM-SCH-13
def test_sorm_sch_13__thirteen_digits_two_decimals_pass(s):
    """SORM-SCH-13 — 13 integer digits and 2 decimals pass in quantity and price.
    Rules: validate_and_build_items R10 (the valid side of both limits)."""
    result = SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99"))
    # Then 1
    assert result.quantity_returned == Decimal("9999999999999.99")
    # Then 2
    assert result.unit_price == Decimal("9999999999999.99")


# [claude] SORM-SCH-14
def test_sorm_sch_14__trailing_zero_decimals_pass(s):
    """SORM-SCH-14 — a whole quantity with trailing zero decimals passes.
    Rules: validate_and_build_items R10 (`"5.00"` has 2 decimals)."""
    result = SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("5.00"), unit_price=Decimal("2.50"))
    # Then 1
    assert result.quantity_returned == Decimal("5.00")
    # Then 2
    assert result.unit_price == Decimal("2.50")


# [claude] SORM-SCH-16
def test_sorm_sch_16__only_return_type_and_items_required(s):
    """SORM-SCH-16 — only `return_type` and `items` are required on the return.
    Rules: validate_and_build_items Inputs (G2)."""
    result = SalesOrderReturnCreate(return_type="refund", items=_one())
    # Then 1
    assert result.reason is None
    # Then 2
    assert result.notes is None
    # Then 3
    assert len(result.items) == 1


# [claude] SORM-SCH-17
def test_sorm_sch_17__line_without_quantity_refused(s):
    """SORM-SCH-17 — a line without a quantity is refused.
    Rules: validate_and_build_items Inputs (G2: line id and quantity required)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(so_item_id=1)
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("quantity_returned",)


# [claude] SORM-SCH-18
def test_sorm_sch_18__line_without_order_line_id_refused(s):
    """SORM-SCH-18 — a line without the order line id is refused.
    Rules: validate_and_build_items Inputs (G2)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SalesOrderReturnItemCreate(quantity_returned=Decimal("1"))
    # Then 2
    assert exc.value.errors()[0]["loc"] == ("so_item_id",)


# =========================================================================== #
# get_return
# =========================================================================== #


# [claude] SORM-G-01
def test_sorm_g_01__pending_return_returned(db, s):
    """SORM-G-01 — a pending return of this order is returned.
    Rules: get_return R1."""
    r = mk_return(db, s, "001")
    result = RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, SalesOrderReturn)
    # Then 2
    assert result.id == r.id
    # Then 3
    assert result.status == "pending"


# [claude] SORM-G-02
def test_sorm_g_02__completed_return_returned(db, s):
    """SORM-G-02 — a completed return is returned too.
    Rules: get_return R1 (any status)."""
    rc = mk_return(db, s, "001", **completed(s))
    result = RM.get_return(db, return_id=rc.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == rc.id
    # Then 2
    assert result.status == "completed"
    assert result.completed_by == s.U1.id


# [claude] SORM-G-03
def test_sorm_g_03__unknown_id_404(db, s):
    """SORM-G-03 — an unknown id is 404.
    Rules: get_return R2; Errors row 1."""
    mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=MISSING, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Return with ID 999999999 not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-04
def test_sorm_g_04__lower_order_return_404(db, s):
    """SORM-G-04 — a return of the lower-id order is 404 when asked under this order.
    Rules: get_return R2."""
    ra = mk_return(db, s, "001", sales_order_id=s.O1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=ra.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {ra.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-05
def test_sorm_g_05__higher_order_return_404(db, s):
    """SORM-G-05 — a return of the higher-id order is 404 when asked under this order.
    Rules: get_return R2."""
    rc3 = mk_return(db, s, "003", sales_order_id=s.O3.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=rc3.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {rc3.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-06
def test_sorm_g_06__w0_return_on_this_order_404(db, s):
    """SORM-G-06 — a W0 return on this order id is 404.
    Rules: get_return R2 (HR-16)."""
    r0 = mk_return(db, s, "000", workspace_id=s.W0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=r0.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {r0.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-07
def test_sorm_g_07__w2_return_on_this_order_404(db, s):
    """SORM-G-07 — a W2 return on this order id is 404.
    Rules: get_return R2 (HR-16)."""
    r9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=r9.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {r9.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-08
def test_sorm_g_08__w1_return_404_from_w0(db, s):
    """SORM-G-08 — a W1 return is 404 to a caller in W0.
    Rules: get_return R2 (workspace gate, lower side)."""
    r = mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {r.id} not found"


# [claude] SORM-G-09
def test_sorm_g_09__default_read_no_write_no_lock(db, s):
    """SORM-G-09 — the default read writes nothing and takes no lock.
    Rules: get_return R3, R4 (default `False` reads without a lock)."""
    r = mk_return(db, s, "001")
    r_id, o2, w1 = r.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.get_return(db, return_id=r_id, sales_order_id=o2, workspace_id=w1)
        # Then 1
        assert result.id == r_id
        # Then 2
        assert_session_clean(db)
        # Then 3
        assert rec.written == []
        # Then 4
        assert rec.no_lock()


# [claude] SORM-G-10
@X2764
def test_sorm_g_10__for_update_true_locks_return_row(db, s):
    """SORM-G-10 — `for_update=True` reads the return row with a lock.
    Rules: get_return R4 [BUG-2764] (HR-10)."""
    r = mk_return(db, s, "001")
    r_id, o2, w1 = r.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.get_return(db, return_id=r_id, sales_order_id=o2, workspace_id=w1, for_update=True)
        # Then 1
        assert result.id == r_id
        # Then 2
        assert result.status == "pending"
        # Then 3
        assert rec.locks("sales_order_returns")
        # Then 4
        assert rec.written == []


# [claude] SORM-G-11
@X2764
def test_sorm_g_11__for_update_still_refuses_other_workspace(db, s):
    """SORM-G-11 — `for_update=True` still refuses a return of another workspace.
    Rules: get_return R2, R4 [BUG-2764]."""
    r9 = mk_return(db, s, "009", workspace_id=s.W2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=r9.id, sales_order_id=s.O2.id, workspace_id=s.W1.id, for_update=True)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {r9.id} not found"
    # Then 3
    assert_session_clean(db)


# [claude] SORM-G-12
@X2764
def test_sorm_g_12__for_update_false_unlocked(db, s):
    """SORM-G-12 — `for_update=False` is the unlocked read.
    Rules: get_return R4 [BUG-2764]."""
    r = mk_return(db, s, "001")
    r_id, o2, w1 = r.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.get_return(db, return_id=r_id, sales_order_id=o2, workspace_id=w1, for_update=False)
        # Then 1
        assert result.id == r_id
        # Then 2
        assert rec.no_lock()


# [claude] SORM-G-13
@X2765
def test_sorm_g_13__lines_read_in_id_order(db, s):
    """SORM-G-13 — the return's lines are read in id order.
    Rules: get_return R5 [BUG-2765] (HR-6)."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    a = mk_rline(db, r, l1, "1.00")
    b = mk_rline(db, r, l1, "2.00")
    r_id, a_id, b_id, o2, w1 = r.id, a.id, b.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.get_return(db, return_id=r_id, sales_order_id=o2, workspace_id=w1)
        lines = list(result.items)
        # Then 1
        assert sorted(x.id for x in lines) == [a_id, b_id]
        # Then 2
        assert any("sales_order_return_items.id" in order_part(st) for st in rec.sel("sales_order_return_items"))


# [claude] SORM-G-14
@X2765_NS
def test_sorm_g_14__lines_in_id_order_after_update(db, s):
    """SORM-G-14 — the return's lines come back in id order after an update moves one.
    Rules: get_return R5 [BUG-2765]."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    a = mk_rline(db, r, l1, "1.00")
    b = mk_rline(db, r, l1, "2.00")
    c = mk_rline(db, r, l1, "3.00")
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_l(db, a)
    result = RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [x.id for x in result.items] == [a_id, b_id, c_id]


# [claude] SORM-G-15
def test_sorm_g_15__voided_return_returned(db, s):
    """SORM-G-15 — a voided return is returned too.
    Rules: get_return R1 (any status)."""
    rv = mk_return(db, s, "002", **VOIDED)
    result = RM.get_return(db, return_id=rv.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == rv.id
    # Then 2
    assert result.status == "voided"


# [claude] SORM-G-16
def test_sorm_g_16__w1_return_404_from_w2(db, s):
    """SORM-G-16 — a W1 return is 404 to a caller in W2.
    Rules: get_return R2 (workspace gate, higher side)."""
    r = mk_return(db, s, "001")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Return with ID {r.id} not found"


# [claude] SORM-G-17
def test_sorm_g_17__lines_are_exactly_its_own(db, s):
    """SORM-G-17 — the return's lines are exactly its own lines.
    Rules: get_return R1, R5 (the part that holds today: which lines, not their order)."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    a = mk_rline(db, r, l1, "1.00")
    b = mk_rline(db, r, l1, "2.00")
    r2 = mk_return(db, s, "002")
    mk_rline(db, r2, l1, "3.00")
    result = RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert sorted(x.id for x in result.items) == [a.id, b.id]
    # Then 2
    assert sorted(x.quantity_returned for x in result.items) == [Decimal("1.00"), Decimal("2.00")]


# =========================================================================== #
# list_returns
# =========================================================================== #


# [claude] SORM-L-01
def test_sorm_l_01__newest_first(db, s):
    """SORM-L-01 — the order's returns come newest first.
    Rules: list_returns R1."""
    ra = mk_return(db, s, "001", created_at=T1)
    rb = mk_return(db, s, "002", created_at=T3)
    rc = mk_return(db, s, "003", created_at=T2)
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [rb.id, rc.id, ra.id]


# [claude] SORM-L-02
def test_sorm_l_02__every_status_listed(db, s):
    """SORM-L-02 — every status is listed.
    Rules: list_returns R1."""
    rp = mk_return(db, s, "001", created_at=T1)
    rc = mk_return(db, s, "002", created_at=T2, **completed(s))
    rv = mk_return(db, s, "003", created_at=T3, **VOIDED)
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [rv.id, rc.id, rp.id]
    # Then 2
    assert [r.status for r in result] == ["voided", "completed", "pending"]


# [claude] SORM-L-03
def test_sorm_l_03__other_orders_not_listed(db, s):
    """SORM-L-03 — returns of the orders on both sides are not listed.
    Rules: list_returns R1."""
    mk_return(db, s, "001", sales_order_id=s.O1.id, created_at=T3)
    rb = mk_return(db, s, "002", created_at=T1)
    mk_return(db, s, "003", sales_order_id=s.O3.id, created_at=T2)
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [rb.id]


# [claude] SORM-L-04
def test_sorm_l_04__w0_and_w2_returns_not_listed(db, s):
    """SORM-L-04 — W0 and W2 returns on this order id are not listed.
    Rules: list_returns R1 (HR-16)."""
    mk_return(db, s, "000", workspace_id=s.W0.id, created_at=T3)
    rb = mk_return(db, s, "002", created_at=T1)
    mk_return(db, s, "009", workspace_id=s.W2.id, created_at=T2)
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [rb.id]


# [claude] SORM-L-05
def test_sorm_l_05__unknown_order_empty(db, s):
    """SORM-L-05 — an unknown order gets an empty list.
    Rules: list_returns R1."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, sales_order_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] SORM-L-06
def test_sorm_l_06__list_no_write_no_lock(db, s):
    """SORM-L-06 — the list writes nothing and takes no lock.
    Rules: list_returns R1 (Side effects: none)."""
    rb = mk_return(db, s, "002")
    rb_id, o2, w1 = rb.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.list_returns(db, sales_order_id=o2, workspace_id=w1)
        # Then 1
        assert [r.id for r in result] == [rb_id]
        # Then 2
        assert_session_clean(db)
        # Then 3
        assert rec.written == []
        # Then 4
        assert rec.no_lock()


# [claude] SORM-L-07
@X2423
def test_sorm_l_07__tie_broken_by_id_desc(db, s):
    """SORM-L-07 — returns of one creation time are broken by id, newest first.
    Rules: list_returns R1 (DAO tie-break, BUG-2423)."""
    ra = mk_return(db, s, "001", created_at=T2)
    rb = mk_return(db, s, "002", created_at=T2)
    ra_id, rb_id, o2, w1 = ra.id, rb.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.list_returns(db, sales_order_id=o2, workspace_id=w1)
        # Then 1
        assert sorted(r.id for r in result) == [ra_id, rb_id]
        # Then 2
        assert any("sales_order_returns.id DESC" in order_part(st) for st in rec.sel("sales_order_returns"))


# [claude] SORM-L-08
@X2765
def test_sorm_l_08__listed_lines_read_in_id_order(db, s):
    """SORM-L-08 — each listed return's lines are read in id order.
    Rules: list_returns R2 [BUG-2765]."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    a = mk_rline(db, r, l1, "1.00")
    b = mk_rline(db, r, l1, "2.00")
    a_id, b_id, o2, w1 = a.id, b.id, s.O2.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = RM.list_returns(db, sales_order_id=o2, workspace_id=w1)
        lines = list(result[0].items)
        # Then 1
        assert sorted(x.id for x in lines) == [a_id, b_id]
        # Then 2
        assert any("sales_order_return_items.id" in order_part(st) for st in rec.sel("sales_order_return_items"))


# [claude] SORM-L-09
@X2765_NS
def test_sorm_l_09__listed_lines_in_id_order_after_update(db, s):
    """SORM-L-09 — listed lines come back in id order after an update moves one.
    Rules: list_returns R2 [BUG-2765]."""
    l1 = mk_line(db, s, 1)
    r = mk_return(db, s, "001")
    a = mk_rline(db, r, l1, "1.00")
    b = mk_rline(db, r, l1, "2.00")
    c = mk_rline(db, r, l1, "3.00")
    a_id, b_id, c_id = a.id, b.id, c.id
    seqscan(db)
    bump_l(db, a)
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [x.id for x in result[0].items] == [a_id, b_id, c_id]


# [claude] SORM-L-10
def test_sorm_l_10__w0_caller_sees_none(db, s):
    """SORM-L-10 — a caller in W0 sees none of W1's returns.
    Rules: list_returns R1 (workspace gate, lower side)."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W0.id)
    # Then 1
    assert result == []


# [claude] SORM-L-11
def test_sorm_l_11__w2_caller_sees_none(db, s):
    """SORM-L-11 — a caller in W2 sees none of W1's returns.
    Rules: list_returns R1 (workspace gate, higher side)."""
    mk_return(db, s, "002")
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W2.id)
    # Then 1
    assert result == []


# [claude] SORM-L-12
def test_sorm_l_12__each_return_carries_its_own_lines(db, s):
    """SORM-L-12 — each listed return carries exactly its own lines.
    Rules: list_returns R1, R2 (the part that holds today: which lines, not their order)."""
    l1 = mk_line(db, s, 1)
    ra = mk_return(db, s, "001", created_at=T1)
    a = mk_rline(db, ra, l1, "1.00")
    b = mk_rline(db, ra, l1, "2.00")
    rb = mk_return(db, s, "002", created_at=T2)
    c = mk_rline(db, rb, l1, "3.00")
    result = RM.list_returns(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [rb.id, ra.id]
    # Then 2
    assert sorted(x.id for x in result[0].items) == [c.id]
    # Then 3
    assert sorted(x.id for x in result[1].items) == [a.id, b.id]


# =========================================================================== #
# sync_return_paid (every return built with updated_at T1, updated_by None)
# =========================================================================== #


def mk_sret(db, s, **cols):
    """`return "001"` with the section's `updated_at T1`, `updated_by None`, plus `cols`."""
    return mk_return(db, s, "001", **{"updated_at": T1, "updated_by": None, **cols})


# [claude] SORM-S-01
def test_sorm_s_01__fully_paid_sets_paid(db, s):
    """SORM-S-01 — a fully paid credit note sets `paid` and reports the change.
    Rules: sync_return_paid R1, R5."""
    cn = mk_cn(db, s, s.W1, "paid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=False)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.paid is True
    # Then 3
    assert row.updated_at != T1
    # Then 4
    assert row.status == "pending"
    assert row.updated_by is None
    assert row.completed_at is None
    assert row.completed_by is None
    assert row.invoice_id == cn.id
    # Then 5
    assert reread(db, AccountInvoice, cn.id).payment_status == "paid"


# [claude] SORM-S-02
def test_sorm_s_02__partly_paid_clears_paid(db, s):
    """SORM-S-02 — a partly paid credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    cn = mk_cn(db, s, s.W1, "partial")
    r = mk_sret(db, s, invoice_id=cn.id, paid=True)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.paid is False
    # Then 3
    assert row.updated_at != T1


# [claude] SORM-S-03
def test_sorm_s_03__unpaid_clears_paid(db, s):
    """SORM-S-03 — an unpaid credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    cn = mk_cn(db, s, s.W1, "unpaid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=True)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, SalesOrderReturn, r.id).paid is False


# [claude] SORM-S-04
def test_sorm_s_04__overdue_clears_paid(db, s):
    """SORM-S-04 — an overdue credit note clears `paid`.
    Rules: sync_return_paid R2, R5."""
    cn = mk_cn(db, s, s.W1, "overdue")
    r = mk_sret(db, s, invoice_id=cn.id, paid=True)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, SalesOrderReturn, r.id).paid is False


# [claude] SORM-S-05
def test_sorm_s_05__still_paid_no_change(db, s):
    """SORM-S-05 — already paid and still paid: no change, nothing flushed.
    Rules: sync_return_paid R4."""
    cn = mk_cn(db, s, s.W1, "paid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=True)
    with StatementRecorder(db) as rec:
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is False
        # Then 2
        assert r not in db.dirty
        # Then 3
        assert rec.written == []
        # Then 4
        row = reread(db, SalesOrderReturn, r.id)
        assert row.paid is True
        assert row.updated_at == T1


# [claude] SORM-S-06
def test_sorm_s_06__still_not_paid_no_change(db, s):
    """SORM-S-06 — not paid and still not paid: no change, nothing flushed.
    Rules: sync_return_paid R4."""
    cn = mk_cn(db, s, s.W1, "partial")
    r = mk_sret(db, s, invoice_id=cn.id, paid=False)
    with StatementRecorder(db) as rec:
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is False
        # Then 2
        assert r not in db.dirty
        # Then 3
        assert rec.written == []
        # Then 4
        row = reread(db, SalesOrderReturn, r.id)
        assert row.paid is False
        assert row.updated_at == T1


# [claude] SORM-S-07
def test_sorm_s_07__no_credit_note_clears_paid(db, s):
    """SORM-S-07 — no credit note: `paid` is cleared.
    Rules: sync_return_paid R3, R5."""
    r = mk_sret(db, s, invoice_id=None, paid=True)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.paid is False
    # Then 3
    assert row.updated_at != T1


# [claude] SORM-S-08
def test_sorm_s_08__no_credit_note_not_paid_nothing_changes(db, s):
    """SORM-S-08 — no credit note and not paid: nothing changes.
    Rules: sync_return_paid R3, R4."""
    r = mk_sret(db, s, invoice_id=None, paid=False)
    with StatementRecorder(db) as rec:
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is False
        # Then 2
        assert rec.written == []
        # Then 3
        row = reread(db, SalesOrderReturn, r.id)
        assert row.paid is False
        assert row.updated_at == T1


# [claude] SORM-S-09
def test_sorm_s_09__w0_paid_invoice_does_not_count(db, s):
    """SORM-S-09 — a paid invoice of W0 does not count as this return's credit note.
    Rules: sync_return_paid R1, R3 (HR-16, lower workspace id)."""
    c0 = mk_cn(db, s, s.W0, "paid")
    r = mk_sret(db, s, invoice_id=c0.id, paid=False)
    before_c0 = snap(db, AccountInvoice, c0.id)
    with StatementRecorder(db) as rec:
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is False
        # Then 2
        assert rec.written == []
        # Then 3
        row = reread(db, SalesOrderReturn, r.id)
        assert row.paid is False
        assert row.updated_at == T1
        # Then 4
        assert snap(db, AccountInvoice, c0.id) == before_c0


# [claude] SORM-S-10
def test_sorm_s_10__w2_paid_invoice_does_not_keep_paid(db, s):
    """SORM-S-10 — a paid invoice of W2 does not keep `paid` set.
    Rules: sync_return_paid R1, R3 (HR-16, higher workspace id)."""
    c9 = mk_cn(db, s, s.W2, "paid")
    r = mk_sret(db, s, invoice_id=c9.id, paid=True)
    before_c9 = snap(db, AccountInvoice, c9.id)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, SalesOrderReturn, r.id).paid is False
    # Then 3
    assert snap(db, AccountInvoice, c9.id) == before_c9


# [claude] SORM-S-11
def test_sorm_s_11__voided_credit_note_clears_paid(db, s):
    """SORM-S-11 — a voided credit note clears `paid`.
    Rules: sync_return_paid R2 (owner freeze: a return credit note is voidable)."""
    cn = voided_cn(db, s)
    r = mk_sret(db, s, invoice_id=cn.id, paid=True)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, SalesOrderReturn, r.id).paid is False
    # Then 3
    inv = reread(db, AccountInvoice, cn.id)
    assert inv.invoice_status == "voided"
    assert inv.payment_status == "unpaid"


# [claude] SORM-S-12
def test_sorm_s_12__completed_return_follows_and_keeps_completion(db, s):
    """SORM-S-12 — a completed return follows its credit note too, and keeps its completion.
    Rules: sync_return_paid R1, R5 (any status; `completed_*` untouched)."""
    cn = mk_cn(db, s, s.W1, "paid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=False, **completed(s))
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.paid is True
    # Then 3
    assert row.status == "completed"
    assert row.completed_at == T4
    assert row.completed_by == s.U1.id
    assert row.updated_by is None


# [claude] SORM-S-13
def test_sorm_s_13__change_flushed_as_one_update(db, s):
    """SORM-S-13 — a change is flushed in the call, as one UPDATE of the return.
    Rules: sync_return_paid R5 (flushed)."""
    cn = mk_cn(db, s, s.W1, "paid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=False)
    with StatementRecorder(db) as rec:
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is True
        # Then 2
        assert r not in db.dirty
        # Then 3
        assert len(rec.written) == 1
        # Then 4
        assert rec.written[0].startswith("UPDATE sales_order_returns")
        # Then 5
        assert rec.no_lock()


# [claude] SORM-S-14
def test_sorm_s_14__change_not_committed(db, s):
    """SORM-S-14 — the change is not committed.
    Rules: sync_return_paid R5 (not committed)."""
    cn = mk_cn(db, s, s.W1, "paid")
    r = mk_sret(db, s, invoice_id=cn.id, paid=False)
    r_id = r.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
        # Then 1
        assert result is True
        # Then 2
        assert reread(db, SalesOrderReturn, r_id).paid is True
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    row = reread(db, SalesOrderReturn, r_id)
    assert row.paid is False
    assert row.updated_at == T1


# =========================================================================== #
# Return price range (R6, R6a) — BUG-2786, owner OQ-45
# =========================================================================== #


def PR(line, q, price, **kw):
    """The Q45 cards' `SalesOrderReturnItemCreate(so_item_id=L.id, quantity_returned=Decimal(q), unit_price=Decimal(p))`."""
    return SalesOrderReturnItemCreate(so_item_id=line.id, quantity_returned=Decimal(q), unit_price=Decimal(price), **kw)


# [claude] SORM-Q45-01
@X2786
def test_sorm_q45_01__negative_price_refused(db, s):
    """SORM-Q45-01 — a negative price is refused.
    Rules: validate_and_build_items R6 [BUG-2786]; Errors row 3."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    before = totals(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l1, "1", "-5")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Return price for "Pump" must be between 0 and 10.00'
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert totals(db) == before


# [claude] SORM-Q45-02
def test_sorm_q45_02__zero_price_accepted(db, s):
    """SORM-Q45-02 — a price of 0 is a price, not "not sent", and is accepted.
    Rules: validate_and_build_items R6 (0 accepted)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(PR(l1, "1", "0")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["unit_price"] == Decimal("0")
    # Then 3
    assert result[0]["unit_price"] is not None


# [claude] SORM-Q45-03
@X2786
def test_sorm_q45_03__price_far_above_refused(db, s):
    """SORM-Q45-03 — a price far above the order line's price is refused.
    Rules: validate_and_build_items R6 [BUG-2786]."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l1, "1", "99999")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Return price for "Pump" must be between 0 and 10.00'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-Q45-04
@X2786
def test_sorm_q45_04__one_hundredth_above_refused(db, s):
    """SORM-Q45-04 — one hundredth above the order line's price is refused.
    Rules: validate_and_build_items R6 [BUG-2786] (over side of the limit)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l1, "1", "10.01")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Return price for "Pump" must be between 0 and 10.00'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-Q45-05
def test_sorm_q45_05__price_inside_range_used(db, s):
    """SORM-Q45-05 — a price inside the range is used instead of the line's.
    Rules: validate_and_build_items R6 (inside the range: used as sent), R8."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(PR(l1, "2", "7.50", notes="restocking fee")))
    # Then 1
    assert result == [{"so_item_id": l1.id, "item_id": s.I1.id, "quantity_returned": Decimal("2"), "unit_price": Decimal("7.50"), "notes": "restocking fee"}]


# [claude] SORM-Q45-06
def test_sorm_q45_06__exactly_line_price_accepted(db, s):
    """SORM-Q45-06 — exactly the order line's price is accepted.
    Rules: validate_and_build_items R6 (equal side of the limit)."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    result = V(db, s, REQ(PR(l1, "1", "10.00")))
    # Then 1
    assert result[0]["unit_price"] == Decimal("10.00")


# [claude] SORM-Q45-09
def test_sorm_q45_09__too_many_beats_bad_price_on_one_line(db, s):
    """SORM-Q45-09 — on one line, too many beats a bad price.
    Rules: validate_and_build_items R6a (quantity before price), R3."""
    l1 = mk_line(db, s, 1)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l1, "11", "99999")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-Q45-10
@X2786
def test_sorm_q45_10__bad_price_first_beats_too_many_second(db, s):
    """SORM-Q45-10 — a bad price on the first line beats too many on the second.
    Rules: validate_and_build_items R1, R6a, R6 [BUG-2786]."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l1, "1", "99999"), LN(l2, "11")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Return price for "Pump" must be between 0 and 10.00'
    # Then 3
    assert_session_clean(db)


# [claude] SORM-Q45-11
def test_sorm_q45_11__too_many_first_beats_bad_price_second(db, s):
    """SORM-Q45-11 — too many on the first line beats a bad price on the second.
    Rules: validate_and_build_items R1, R6a."""
    l1 = mk_line(db, s, 1)
    l2 = mk_line(db, s, 2)
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(LN(l1, "11"), PR(l2, "1", "99999")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == TOO("11", "Pump", "10.00")
    # Then 3
    assert_session_clean(db)


# [claude] SORM-Q45-12
@X2786
def test_sorm_q45_12__price_message_names_free_line_and_stored_price(db, s):
    """SORM-Q45-12 — the price message names the free-text line by its description and gives its stored price.
    Rules: validate_and_build_items R6 [BUG-2786]; Errors row 3."""
    mk_line(db, s, 1)
    l3 = mk_free(db, s, "Install fee", unit_price=Decimal("4.50"), line_total=Decimal("45.00"))
    db.expire_all()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        V(db, s, REQ(PR(l3, "1", "4.51")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == 'Return price for "Install fee" must be between 0 and 4.50'
    # Then 3
    assert_session_clean(db)


# =========================================================================== #
# Credit-note void and the return (sync_return_paid R6) — BUG-2788, owner OQ-47
# =========================================================================== #


# [claude] SORM-Q47-01
def test_sorm_q47_01__pending_voided_cn_writes_only_paid(db, s):
    """SORM-Q47-01 — `sync_return_paid` on a pending return with a voided credit note writes only `paid`.
    Rules: sync_return_paid R5, R6 (this method writes only `paid`)."""
    cn = voided_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id, paid=True, updated_at=T1)
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.paid is False
    # Then 3
    assert row.status == "pending"
    assert row.completed_at is None
    assert row.completed_by is None


# [claude] SORM-Q47-02
def test_sorm_q47_02__completed_voided_cn_writes_only_paid(db, s):
    """SORM-Q47-02 — `sync_return_paid` on a completed return with a voided credit note writes only `paid`.
    Rules: sync_return_paid R5, R6 (this method writes only `paid`)."""
    cn = voided_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id, paid=True, updated_at=T1, **completed(s))
    result = RM.sync_return_paid(db, ret=r, workspace_id=s.W1.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.status == "completed"
    assert row.completed_at == T4


# [claude] SORM-Q47-03
@X2788
def test_sorm_q47_03__voided_cn_frees_order(db, s):
    """SORM-Q47-03 — after its credit note is voided, the pending return no longer keeps the order open.
    Rules: sync_return_paid R6 [BUG-2788]; has_open_return R1."""
    cn = confirmed_cn(db, s)
    mk_return(db, s, "001", invoice_id=cn.id)
    void_step(db, s, cn)
    result = RM.has_open_return(db, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is False


# [claude] SORM-Q47-04
@X2788
def test_sorm_q47_04__voided_cn_frees_quantity(db, s):
    """SORM-Q47-04 — after its credit note is voided, the pending return no longer reserves its quantity.
    Rules: sync_return_paid R6 [BUG-2788]; validate_and_build_items R4."""
    l1 = mk_line(db, s, 1)
    cn = confirmed_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id)
    mk_rline(db, r, l1, "4.00")
    void_step(db, s, cn)
    result = V(db, s, REQ(LN(l1, "10")))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["quantity_returned"] == Decimal("10")


# [claude] SORM-Q47-05
@X2788
def test_sorm_q47_05__voided_cn_return_served_voided(db, s):
    """SORM-Q47-05 — after its credit note is voided, the return is served as voided (no longer completable).
    Rules: sync_return_paid R6 [BUG-2788]; get_return R1."""
    cn = confirmed_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id)
    void_step(db, s, cn)
    result = RM.get_return(db, return_id=r.id, sales_order_id=s.O2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == r.id
    # Then 2
    assert result.status == "voided"
    # Then 3
    assert result.paid is False


# [claude] SORM-Q47-06
@X2788
def test_sorm_q47_06__void_marks_pending_return_voided_unpaid(db, s):
    """SORM-Q47-06 — voiding a pending return's credit note marks the return voided, unpaid.
    Rules: sync_return_paid R6 [BUG-2788] (via `void_invoice` R3c)."""
    cn = confirmed_cn(db, s, payment_status="paid")
    r = mk_return(db, s, "001", invoice_id=cn.id, paid=True, updated_at=T1)
    result = AIM.void_invoice(db, invoice_id=cn.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    # Then 1
    assert result.id == cn.id
    # Then 2
    row = reread(db, SalesOrderReturn, r.id)
    assert row.status == "voided"
    # Then 3
    assert row.paid is False
    assert row.completed_at is None
    assert row.completed_by is None


# [claude] SORM-Q47-07
@X2788
def test_sorm_q47_07__void_of_completed_return_cn_refused(db, s):
    """SORM-Q47-07 — voiding a completed return's credit note is refused, nothing changes.
    Rules: sync_return_paid R6 [BUG-2788] (via `void_invoice` R3c)."""
    cn = confirmed_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id, updated_at=T1, **completed(s))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AIM.void_invoice(db, invoice_id=cn.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "This return is completed — its goods have already moved. Start a new return or issue a separate credit note."
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert reread(db, AccountInvoice, cn.id).invoice_status == "confirmed"
    # Then 5
    row = reread(db, SalesOrderReturn, r.id)
    assert row.status == "completed"
    assert row.completed_at == T4
    assert row.updated_at == T1


# [claude] SORM-Q47-08
def test_sorm_q47_08__void_of_voided_return_cn_leaves_return(db, s):
    """SORM-Q47-08 — voiding the credit note of an already voided return leaves the return as it is.
    Rules: sync_return_paid R6 (void_invoice R3c: already voided → return unchanged)."""
    cn = confirmed_cn(db, s)
    r = mk_return(db, s, "001", invoice_id=cn.id, **VOIDED)
    result = AIM.void_invoice(db, invoice_id=cn.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Typo")
    # Then 1
    assert result.id == cn.id
    # Then 2
    assert reread(db, AccountInvoice, cn.id).invoice_status == "voided"
    # Then 3
    row = reread(db, SalesOrderReturn, r.id)
    assert row.status == "voided"
    assert row.paid is False
    assert row.updated_at == T4
