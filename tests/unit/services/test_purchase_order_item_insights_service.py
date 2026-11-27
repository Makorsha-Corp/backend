"""Unit tests for app/services/purchase_order_item_insights_service.py.

Implements tests/unit/services/purchase_order_item_insights_service.cases.md
(revision 4), one test per card, in card order. Real Postgres session (`db`
fixture), rolled back after each test. Nothing is patched except what
Conventions name: the CLOCK / SKEW clocks and the commit / rollback spies.

DB tests request the Standing rows fixture `st`; helper cards (D, R, L, M, A)
build no rows. Card row names are lower-case attributes (`I1.id` ->
`st.i1.id`); `# Then N` marks the checks of the card's Then line N.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

import app.services.purchase_order_item_insights_service as mod
from app.models.account import Account
from app.models.item import Item
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.status import Status
from app.schemas.purchase_order_item_insights import ItemPriceInsightRef
from app.services.purchase_order_item_insights_service import (
    _dec,
    _HistoryLine,
    _to_ref,
    purchase_order_item_insights_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = purchase_order_item_insights_service
MISSING = 999999999
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
TODAY = date(2026, 6, 15)

B2540 = "BUG-2540: PO price history shows another workspace's supplier and counts another workspace's lines"
B2541 = "BUG-2541: PO price history gives a row for another workspace's item"
B2542 = 'BUG-2542: "Last 30 / 90 days" price windows count from the server\'s local date'
B2543 = 'BUG-2543: "Lowest average supplier" tie goes to whichever supplier the database returns first'


# Convention "HL(...)": a hand-made history line
def HL(line_id, purchase_order_id, unit_price, order_date, account_id=None,
       account_name=None, quantity_ordered=Decimal("1.00"), item_id=1):
    return _HistoryLine(
        item_id=item_id, line_id=line_id, purchase_order_id=purchase_order_id,
        po_number=f"PO-{purchase_order_id}", account_id=account_id,
        account_name=account_name, unit_price=unit_price,
        quantity_ordered=quantity_ordered, order_date=order_date,
    )


# --------------------------------------------------------------------------- #
# Conventions -> Clocks
# --------------------------------------------------------------------------- #

@contextmanager
def clock(local, utc):
    """clock(local, utc): the module's `date.today()` says `local`; the module's
    own `utcnow` (read after BUG-2542) says `utc`."""
    class FixedDate(date):
        @classmethod
        def today(cls):
            return local

    with ExitStack() as stack:
        stack.enter_context(patch.object(mod, "date", FixedDate))
        stack.enter_context(patch(
            "app.services.purchase_order_item_insights_service.utcnow",
            return_value=utc, create=True,
        ))
        yield


def CLOCK():
    return clock(date(2026, 6, 15), datetime(2026, 6, 15, 12, 0))  # noqa: DTZ001


def SKEW():
    return clock(date(2026, 6, 16), datetime(2026, 6, 15, 20, 0))  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #

def ids(lines):
    return {x.line_id for x in lines}


def item_ids(result):
    return [r.item_id for r in result.items]


@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, \
            patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield SimpleNamespace(cm=cm, rb=rb)


def counts(db):
    """Convention "nothing written": purchase_orders and purchase_order_items rows."""
    return (
        db.scalar(select(func.count()).select_from(PurchaseOrder)),
        db.scalar(select(func.count()).select_from(PurchaseOrderItem)),
    )


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (built in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def st(db):
    s = SimpleNamespace(db=db)
    s.w0 = make_workspace(db)
    s.w1 = make_workspace(db)
    s.w2 = make_workspace(db)
    s.u1 = make_profile(db)
    s.s0 = _add(db, Status(workspace_id=s.w0.id, name="Open", comment=""))
    s.s1 = _add(db, Status(workspace_id=s.w1.id, name="Open", comment=""))
    s.s9 = _add(db, Status(workspace_id=s.w2.id, name="Open", comment=""))
    for attr, ws, name in (("i0", s.w0, "Zero Bolt"), ("i1", s.w1, "Bolt"), ("i2", s.w1, "Nut"),
                           ("i3", s.w1, "Washer"), ("i9", s.w2, "Far Bolt")):
        setattr(s, attr, _add(db, Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs")))
    for attr, ws, name in (("ac0", s.w0, "Zero Co"), ("ac1", s.w1, "Acme"),
                           ("ac2", s.w1, "Beta"), ("ac9", s.w2, "Far Co")):
        setattr(s, attr, _add(db, Account(workspace_id=ws.id, name=name)))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def po(st, po_number, *, ws=1, voided=False, **cols):
    """Convention "po" (ws=1), "W0 po" (ws=0), "W2 po" (ws=2); `voided=True`
    writes every void column. `cols` are the columns the card names."""
    w, s = {0: (st.w0, st.s0), 1: (st.w1, st.s1), 2: (st.w2, st.s9)}[ws]
    fields = {"workspace_id": w.id, "po_number": po_number, "destination_type": "storage",
              "destination_id": 1, "current_status_id": s.id, "created_by": st.u1.id}
    if voided:
        fields.update(voided=True, void_note="Void", voided_at=T0, voided_by=st.u1.id)
    fields.update(cols)
    return _add(st.db, PurchaseOrder(**fields))


def ln(st, p, item, unit_price, **cols):
    """Convention "ln of P": a line of P for `item` at `unit_price`."""
    fields = {"workspace_id": p.workspace_id, "purchase_order_id": p.id, "line_number": 1,
              "item_id": item.id, "quantity_ordered": Decimal("1.00"), "unit_price": unit_price}
    fields.update(cols)
    return _add(st.db, PurchaseOrderItem(**fields))


def insights(db, st, p):
    return svc.get_item_price_insights(db, po_id=p.id, workspace_id=st.w1.id)


def fetch(db, st, item_list, exclude_po_id=MISSING):
    return svc._fetch_history_lines(db, workspace_id=st.w1.id, item_ids=item_list, exclude_po_id=exclude_po_id)


# =========================================================================== #
# _dec
# =========================================================================== #

def test_pii_d_01__none_gives_zero():
    """PII-D-01 — None gives zero.
    Rules: _dec R1."""
    result = _dec(None)
    # Then 1
    assert result == Decimal(0)
    # Then 2
    assert isinstance(result, Decimal)


def test_pii_d_02__decimal_keeps_scale():
    """PII-D-02 — a Decimal keeps its scale.
    Rules: _dec R2."""
    result = _dec(Decimal("10.00"))
    # Then 1
    assert str(result) == "10.00"


def test_pii_d_03__float_through_text_int_whole():
    """PII-D-03 — a float goes through its text, an int stays whole.
    Rules: _dec R2."""
    result = (_dec(1.1), _dec(3))
    # Then 1
    assert str(result[0]) == "1.1"
    # Then 2
    assert str(result[1]) == "3"


def test_pii_d_04__not_a_number_raises():
    """PII-D-04 — text that is not a number raises.
    Rules: _dec Errors."""
    # Then 1
    with pytest.raises(InvalidOperation):
        _dec("abc")


# =========================================================================== #
# _to_ref
# =========================================================================== #

def test_pii_r_01__reference_copies_six_fields():
    """PII-R-01 — the reference copies the six fields.
    Rules: _to_ref R1."""
    line = HL(line_id=7, purchase_order_id=5, unit_price=Decimal("12.50"), order_date=date(2026, 3, 4),
              account_id=11, account_name="Acme", quantity_ordered=Decimal("4.00"), item_id=3)
    result = _to_ref(line)
    # Then 1
    assert isinstance(result, ItemPriceInsightRef)
    # Then 2
    assert result.purchase_order_id == 5
    assert result.po_number == "PO-5"
    assert result.account_id == 11
    assert result.account_name == "Acme"
    # Then 3
    assert result.unit_price == Decimal("12.50")
    assert str(result.unit_price) == "12.50"
    assert result.order_date == date(2026, 3, 4)
    # Then 4
    assert set(result.model_dump()) == {
        "purchase_order_id", "po_number", "account_id", "account_name", "unit_price", "order_date",
    }


def test_pii_r_02__none_values_stay_none():
    """PII-R-02 — None values stay None.
    Rules: _to_ref R1."""
    line = HL(line_id=7, purchase_order_id=5, unit_price=None, order_date=None)
    result = _to_ref(line)
    # Then 1
    assert result.account_id is None
    assert result.account_name is None
    # Then 2
    assert result.unit_price is None
    assert result.order_date is None


# =========================================================================== #
# get_item_price_insights
# =========================================================================== #

def test_pii_g_01__unknown_po_404_nothing_changes(db, st):
    """PII-G-01 — an unknown PO id is 404 and nothing changes.
    Rules: get_item_price_insights R1, R7; Errors row 1."""
    po(st, "PO-1")
    db.commit()
    before = counts(db)
    # Then 1
    with spies(db) as sp, pytest.raises(HTTPException) as exc:
        svc.get_item_price_insights(db, po_id=MISSING, workspace_id=st.w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Purchase order with ID 999999999 not found"
    # Then 2
    assert sp.cm.call_count == 0
    # Then 3
    assert sp.rb.call_count == 0
    # Then 4
    assert counts(db) == before


def test_pii_g_02__po_of_later_workspace_404(db, st):
    """PII-G-02 — a PO of a later workspace is 404.
    Rules: get_item_price_insights R1; Errors row 1."""
    po(st, "PO-1")
    p9 = po(st, "PO-9", ws=2)
    ln(st, p9, st.i9, Decimal("5.00"))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        insights(db, st, p9)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Purchase order with ID {p9.id} not found"
    # Then 2
    assert counts(db) == before


def test_pii_g_03__po_of_earlier_workspace_404(db, st):
    """PII-G-03 — a PO of an earlier workspace is 404.
    Rules: get_item_price_insights R1; Errors row 1."""
    p0 = po(st, "PO-0", ws=0)
    ln(st, p0, st.i0, Decimal("5.00"))
    po(st, "PO-1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        insights(db, st, p0)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Purchase order with ID {p0.id} not found"
    # Then 2
    assert counts(db) == before


def test_pii_g_04__voided_po_is_answered(db, st):
    """PII-G-04 — a voided PO is answered.
    Rules: get_item_price_insights R1."""
    pv = po(st, "PO-V", voided=True)
    ln(st, pv, st.i1, Decimal("5.00"))
    result = insights(db, st, pv)
    row = result.items[0]
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert row.last_ordered is None
    assert row.lowest.all_time is None


def test_pii_g_05__po_with_no_lines_gives_no_rows(db, st):
    """PII-G-05 — a PO with no lines gives no rows.
    Rules: get_item_price_insights R2."""
    p1 = po(st, "PO-1")
    p2 = po(st, "PO-2")
    ln(st, p2, st.i1, Decimal("5.00"))
    result = insights(db, st, p1)
    # Then 1
    assert result.items == []


def test_pii_g_06__line_with_later_workspace_id_not_seen(db, st):
    """PII-G-06 — a line with a later workspace's workspace_id is not seen.
    Rules: get_item_price_insights R3."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("5.00"), workspace_id=st.w2.id)
    result = insights(db, st, p1)
    # Then 1
    assert result.items == []


def test_pii_g_07__line_with_earlier_workspace_id_not_seen(db, st):
    """PII-G-07 — a line with an earlier workspace's workspace_id is not seen.
    Rules: get_item_price_insights R3."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i2, Decimal("5.00"), workspace_id=st.w0.id)
    ln(st, p1, st.i3, Decimal("6.00"), line_number=2)
    result = insights(db, st, p1)
    # Then 1
    assert item_ids(result) == [st.i3.id]


def test_pii_g_08__five_references_each_own_line(db, st):
    """PII-G-08 — the five references each point at their own line.
    Rules: get_item_price_insights R4, R5, R6; _pick_last_ordered R2;
    _pick_min_price_ref R1, R4; _pick_avg_supplier_lowest R1, R4."""
    pc = po(st, "PO-C", account_id=st.ac1.id, order_date=date(2026, 6, 14))
    ln(st, pc, st.i1, Decimal("0.50"))
    h1 = po(st, "PO-H1", order_date=date(2026, 1, 10))
    ln(st, h1, st.i1, Decimal("4.00"))
    h2 = po(st, "PO-H2", account_id=st.ac1.id, order_date=date(2026, 4, 1))
    ln(st, h2, st.i1, Decimal("5.00"))
    h3 = po(st, "PO-H3", account_id=st.ac1.id, order_date=date(2026, 6, 1))
    ln(st, h3, st.i1, Decimal("30.00"))
    h4 = po(st, "PO-H4", order_date=date(2026, 6, 20))
    ln(st, h4, st.i1, None)
    h5 = po(st, "PO-H5", account_id=st.ac2.id, order_date=date(2026, 2, 1))
    ln(st, h5, st.i1, Decimal("7.00"))
    h6 = po(st, "PO-H6", order_date=date(2026, 6, 10))
    ln(st, h6, st.i1, Decimal("12.00"))
    with CLOCK():
        result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert row.last_ordered.purchase_order_id == h4.id
    assert row.last_ordered.unit_price is None
    assert row.last_ordered.order_date == date(2026, 6, 20)
    # Then 3
    assert row.lowest.avg_supplier.purchase_order_id == h5.id
    assert row.lowest.avg_supplier.account_id == st.ac2.id
    assert row.lowest.avg_supplier.account_name == "Beta"
    # Then 4
    assert row.lowest.all_time.purchase_order_id == h1.id
    assert row.lowest.all_time.unit_price == Decimal("4.00")
    assert row.lowest.all_time.account_id is None
    # Then 5
    assert row.lowest.days_30.purchase_order_id == h6.id
    assert row.lowest.days_30.po_number == "PO-H6"
    assert row.lowest.days_30.unit_price == Decimal("12.00")
    # Then 6
    assert row.lowest.days_90.purchase_order_id == h2.id
    assert row.lowest.days_90.account_name == "Acme"
    assert str(row.lowest.days_90.unit_price) == "5.00"
    assert row.lowest.days_90.order_date == date(2026, 4, 1)


def test_pii_g_09__item_with_no_history_all_empty(db, st):
    """PII-G-09 — an item with no history has all five empty.
    Rules: get_item_price_insights R4."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i2, Decimal("5.00"))
    p2 = po(st, "PO-2")
    ln(st, p2, st.i1, Decimal("3.00"))
    result = insights(db, st, p1)
    row = result.items[0]
    # Then 1
    assert item_ids(result) == [st.i2.id]
    # Then 2
    assert row.last_ordered is None
    assert row.lowest.avg_supplier is None
    assert row.lowest.all_time is None
    # Then 3
    assert row.lowest.days_30 is None
    assert row.lowest.days_90 is None


def test_pii_g_10__one_row_per_item_in_id_order(db, st):
    """PII-G-10 — one row per item, in item_id order.
    Rules: get_item_price_insights R3."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i3, Decimal("5.00"), line_number=1)
    ln(st, p1, st.i1, Decimal("6.00"), line_number=2)
    ln(st, p1, st.i1, Decimal("7.00"), line_number=3)
    result = insights(db, st, p1)
    # Then 1
    assert item_ids(result) == [st.i1.id, st.i3.id]


def test_pii_g_11__w1_item_keeps_row_next_to_foreign_item(db, st):
    """PII-G-11 — the W1 item keeps its row next to a foreign item.
    Rules: get_item_price_insights R3, R3a (regression part)."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i9, Decimal("5.00"), line_number=1)
    ln(st, p1, st.i1, Decimal("6.00"), line_number=2)
    result = insights(db, st, p1)
    # Then 1
    assert st.i1.id in item_ids(result)


@pytest.mark.xfail(strict=True, reason=B2541)
def test_pii_g_12__later_workspace_item_gives_no_row(db, st):
    """PII-G-12 — a later workspace's item on the PO gives no row.
    Rules: get_item_price_insights R3a [BUG-2541]."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i9, Decimal("5.00"), line_number=1)
    ln(st, p1, st.i1, Decimal("6.00"), line_number=2)
    result = insights(db, st, p1)
    # Then 1
    assert st.i1.id in item_ids(result)
    # Then 2
    assert item_ids(result) == [st.i1.id]


@pytest.mark.xfail(strict=True, reason=B2541)
def test_pii_g_13__earlier_workspace_item_gives_no_row(db, st):
    """PII-G-13 — an earlier workspace's item on the PO gives no row.
    Rules: get_item_price_insights R3a [BUG-2541]."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("6.00"), line_number=1)
    ln(st, p1, st.i0, Decimal("5.00"), line_number=2)
    result = insights(db, st, p1)
    # Then 1
    assert st.i1.id in item_ids(result)
    # Then 2
    assert item_ids(result) == [st.i1.id]


@pytest.mark.xfail(strict=True, reason=B2541)
def test_pii_g_14__po_with_only_foreign_item_gives_no_rows(db, st):
    """PII-G-14 — a PO holding only a foreign item gives no rows.
    Rules: get_item_price_insights R3a [BUG-2541]."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i9, Decimal("5.00"))
    result = insights(db, st, p1)
    # Then 1
    assert result.items == []


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_g_15__later_workspace_supplier_never_wins_average(db, st):
    """PII-G-15 — a later workspace's supplier never wins the lowest average.
    Rules: get_item_price_insights R4; _fetch_history_lines R4a [BUG-2540]."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    hx = po(st, "PO-X", account_id=st.ac9.id, order_date=date(2026, 1, 5))
    ln(st, hx, st.i1, Decimal("1.00"))
    ha = po(st, "PO-A", account_id=st.ac1.id, order_date=date(2026, 1, 6))
    ln(st, ha, st.i1, Decimal("5.00"))
    result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.all_time.purchase_order_id == hx.id
    # Then 2
    assert row.last_ordered.purchase_order_id == ha.id
    # Then 3
    assert row.lowest.avg_supplier.account_id == st.ac1.id
    assert row.lowest.avg_supplier.purchase_order_id == ha.id
    # Then 4
    assert row.lowest.all_time.account_id is None
    assert row.lowest.all_time.account_name is None


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_g_16__earlier_workspace_supplier_never_wins_average(db, st):
    """PII-G-16 — an earlier workspace's supplier never wins the lowest average.
    Rules: get_item_price_insights R4; _fetch_history_lines R4a [BUG-2540]."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    ha = po(st, "PO-A", account_id=st.ac1.id, order_date=date(2026, 1, 6))
    ln(st, ha, st.i1, Decimal("5.00"))
    hx = po(st, "PO-X", account_id=st.ac0.id, order_date=date(2026, 1, 5))
    ln(st, hx, st.i1, Decimal("1.00"))
    result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.all_time.purchase_order_id == hx.id
    # Then 2
    assert row.lowest.avg_supplier.account_id == st.ac1.id
    assert row.lowest.avg_supplier.purchase_order_id == ha.id
    # Then 3
    assert row.lowest.all_time.account_name is None


def test_pii_g_17__other_workspace_and_voided_history_left_out(db, st):
    """PII-G-17 — history of other workspaces' POs and voided POs is left out.
    Rules: get_item_price_insights R5; _fetch_history_lines R1."""
    h0 = po(st, "PO-0", ws=0, order_date=date(2026, 5, 3))
    ln(st, h0, st.i1, Decimal("1.00"))
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("0.50"))
    ha = po(st, "PO-A", order_date=date(2026, 5, 1))
    ln(st, ha, st.i1, Decimal("5.00"))
    hv = po(st, "PO-V", voided=True, order_date=date(2026, 5, 4))
    ln(st, hv, st.i1, Decimal("2.00"))
    h9 = po(st, "PO-9", ws=2, order_date=date(2026, 5, 5))
    ln(st, h9, st.i1, Decimal("3.00"))
    result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.all_time.purchase_order_id == ha.id
    assert row.lowest.all_time.unit_price == Decimal("5.00")
    # Then 2
    assert row.last_ordered.purchase_order_id == ha.id


def test_pii_g_18__today_minus_30_in_minus_31_out(db, st):
    """PII-G-18 — today−30 is in the 30-day window, today−31 is not.
    Rules: get_item_price_insights R6."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    ha = po(st, "PO-A", order_date=date(2026, 5, 16))
    ln(st, ha, st.i1, Decimal("5.00"))
    hb = po(st, "PO-B", order_date=date(2026, 5, 15))
    ln(st, hb, st.i1, Decimal("1.00"))
    with CLOCK():
        result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.days_30.purchase_order_id == ha.id
    # Then 2
    assert row.lowest.days_90.purchase_order_id == hb.id


def test_pii_g_19__today_in_both_windows_tomorrow_only_all_time(db, st):
    """PII-G-19 — today is in both windows, tomorrow only in all-time.
    Rules: get_item_price_insights R6; _pick_min_price_ref R5."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    ha = po(st, "PO-A", order_date=date(2026, 6, 15))
    ln(st, ha, st.i1, Decimal("5.00"))
    hb = po(st, "PO-B", order_date=date(2026, 6, 16))
    ln(st, hb, st.i1, Decimal("1.00"))
    with CLOCK():
        result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.all_time.purchase_order_id == hb.id
    # Then 2
    assert row.lowest.days_30.purchase_order_id == ha.id
    # Then 3
    assert row.lowest.days_90.purchase_order_id == ha.id


def test_pii_g_20__today_minus_90_in_minus_91_out(db, st):
    """PII-G-20 — today−90 is in the 90-day window, today−91 is not.
    Rules: get_item_price_insights R6."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    ha = po(st, "PO-A", order_date=date(2026, 3, 17))
    ln(st, ha, st.i1, Decimal("5.00"))
    hb = po(st, "PO-B", order_date=date(2026, 3, 16))
    ln(st, hb, st.i1, Decimal("1.00"))
    with CLOCK():
        result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.days_90.purchase_order_id == ha.id
    # Then 2
    assert row.lowest.days_30 is None
    # Then 3
    assert row.lowest.all_time.purchase_order_id == hb.id


def test_pii_g_21__read_leaves_pending_changes_never_commits(db, st):
    """PII-G-21 — a read leaves pending changes pending and never commits.
    Rules: get_item_price_insights R7."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("5.00"))
    p2 = po(st, "PO-2")
    db.commit()
    p2.po_number = "PO-2B"
    db.add(Status(workspace_id=st.w1.id, name="Pending", comment=""))
    with spies(db) as sp:
        result = insights(db, st, p1)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert p2 in db.dirty
    assert len(db.dirty) == 1
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert sp.cm.call_count == 0
    # Then 6
    assert sp.rb.call_count == 0


@pytest.mark.xfail(strict=True, reason=B2542)
def test_pii_g_22__today_is_utc_date_not_local(db, st):
    """PII-G-22 — "today" is the UTC date, not the server's local date.
    Rules: get_item_price_insights R6 [BUG-2542]."""
    pc = po(st, "PO-C")
    ln(st, pc, st.i1, Decimal("9.00"))
    ha = po(st, "PO-A", order_date=date(2026, 5, 16))
    ln(st, ha, st.i1, Decimal("5.00"))
    hb = po(st, "PO-B", order_date=date(2026, 6, 16))
    ln(st, hb, st.i1, Decimal("3.00"))
    with SKEW():
        result = insights(db, st, pc)
    row = result.items[0]
    # Then 1
    assert row.lowest.all_time.purchase_order_id == hb.id
    # Then 2
    assert row.lowest.days_30.purchase_order_id == ha.id
    # Then 3
    assert row.lowest.days_90.purchase_order_id == ha.id


# =========================================================================== #
# _fetch_history_lines
# =========================================================================== #

def test_pii_f_01__history_line_carries_every_field(db, st):
    """PII-F-01 — a history line carries every field.
    Rules: _fetch_history_lines R1, R4, R5."""
    p1 = po(st, "PO-1", account_id=st.ac1.id, order_date=date(2026, 3, 4))
    l1 = ln(st, p1, st.i1, Decimal("12.50"), quantity_ordered=Decimal("3.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].line_id == l1.id
    assert result[0].item_id == st.i1.id
    assert result[0].purchase_order_id == p1.id
    assert result[0].po_number == "PO-1"
    # Then 3
    assert result[0].account_id == st.ac1.id
    assert result[0].account_name == "Acme"
    # Then 4
    assert isinstance(result[0].unit_price, Decimal)
    assert str(result[0].unit_price) == "12.50"
    # Then 5
    assert isinstance(result[0].quantity_ordered, Decimal)
    assert result[0].quantity_ordered == Decimal("3.00")
    # Then 6
    assert result[0].order_date == date(2026, 3, 4)


def test_pii_f_02__voided_po_lines_left_out(db, st):
    """PII-F-02 — lines of a voided PO are left out.
    Rules: _fetch_history_lines R1."""
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    pv = po(st, "PO-V", voided=True)
    ln(st, pv, st.i1, Decimal("1.00"))
    p3 = po(st, "PO-3")
    l3 = ln(st, p3, st.i1, Decimal("6.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id, l3.id}


def test_pii_f_03__excluded_po_left_out_others_kept(db, st):
    """PII-F-03 — the excluded PO's lines are left out, all others kept.
    Rules: _fetch_history_lines R1, R6."""
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    p2 = po(st, "PO-2")
    ln(st, p2, st.i1, Decimal("6.00"))
    ln(st, p2, st.i1, Decimal("6.50"), line_number=2)
    p3 = po(st, "PO-3")
    l3 = ln(st, p3, st.i1, Decimal("7.00"))
    l3b = ln(st, p3, st.i1, None, line_number=2)
    result = fetch(db, st, [st.i1.id], exclude_po_id=p2.id)
    # Then 1
    assert ids(result) == {l1.id, l3.id, l3b.id}


def test_pii_f_04__only_asked_items_returned(db, st):
    """PII-F-04 — only the asked items are returned.
    Rules: _fetch_history_lines R1."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("5.00"), line_number=1)
    l2 = ln(st, p1, st.i2, Decimal("6.00"), line_number=2)
    ln(st, p1, st.i3, Decimal("7.00"), line_number=3)
    result = fetch(db, st, [st.i2.id])
    # Then 1
    assert ids(result) == {l2.id}


def test_pii_f_05__unknown_item_id_matches_nothing(db, st):
    """PII-F-05 — an unknown item id matches nothing.
    Rules: _fetch_history_lines R1."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("5.00"))
    result = fetch(db, st, [MISSING])
    # Then 1
    assert result == []


def test_pii_f_06__other_workspaces_pos_never_returned(db, st):
    """PII-F-06 — POs of earlier and later workspaces are never returned.
    Rules: _fetch_history_lines R1."""
    p0 = po(st, "PO-0", ws=0)
    ln(st, p0, st.i0, Decimal("1.00"))
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    p9 = po(st, "PO-9", ws=2)
    ln(st, p9, st.i9, Decimal("2.00"))
    result = fetch(db, st, [st.i0.id, st.i1.id, st.i9.id])
    # Then 1
    assert ids(result) == {l1.id}


def test_pii_f_07__other_workspaces_pos_with_w1_item_never_returned(db, st):
    """PII-F-07 — other workspaces' POs holding a W1 item are never returned.
    Rules: _fetch_history_lines R1."""
    p0 = po(st, "PO-0", ws=0)
    ln(st, p0, st.i1, Decimal("1.00"))
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    p9 = po(st, "PO-9", ws=2)
    ln(st, p9, st.i1, Decimal("2.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id}


def test_pii_f_08__any_status_counts_unpriced_returned(db, st):
    """PII-F-08 — any status counts and an unpriced line is returned.
    Rules: _fetch_history_lines R2, R5."""
    sd = _add(db, Status(workspace_id=st.w1.id, name="Draft", comment=""))
    sc = _add(db, Status(workspace_id=st.w1.id, name="Complete", comment=""))
    p1 = po(st, "PO-1", current_status_id=sd.id)
    l1 = ln(st, p1, st.i1, None)
    p2 = po(st, "PO-2", current_status_id=sc.id)
    l2 = ln(st, p2, st.i1, Decimal("5.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id, l2.id}
    # Then 2
    assert [x.unit_price for x in result if x.line_id == l1.id] == [None]


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_f_09__line_with_later_workspace_id_left_out(db, st):
    """PII-F-09 — a line with a later workspace's workspace_id is left out.
    Rules: _fetch_history_lines R1a [BUG-2540]."""
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"), line_number=1)
    ln(st, p1, st.i1, Decimal("1.00"), line_number=2, workspace_id=st.w2.id)
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert l1.id in ids(result)
    # Then 2
    assert ids(result) == {l1.id}


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_f_10__line_with_earlier_workspace_id_left_out(db, st):
    """PII-F-10 — a line with an earlier workspace's workspace_id is left out.
    Rules: _fetch_history_lines R1a [BUG-2540]."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("1.00"), line_number=1, workspace_id=st.w0.id)
    l1 = ln(st, p1, st.i1, Decimal("5.00"), line_number=2)
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert l1.id in ids(result)
    # Then 2
    assert ids(result) == {l1.id}


def test_pii_f_11__w1_line_next_to_foreign_line_still_returned(db, st):
    """PII-F-11 — the W1 line next to a foreign line is still returned.
    Rules: _fetch_history_lines R1, R1a (regression part)."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("1.00"), line_number=1, workspace_id=st.w2.id)
    l1 = ln(st, p1, st.i1, Decimal("5.00"), line_number=2)
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert l1.id in ids(result)


def test_pii_f_12__no_order_date_falls_back_to_created_day(db, st):
    """PII-F-12 — no order_date falls back to the UTC day of created_at; a future date is kept.
    Rules: _fetch_history_lines R3."""
    p1 = po(st, "PO-1", created_at=datetime(2026, 3, 4, 23, 30))  # noqa: DTZ001
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    p2 = po(st, "PO-2", order_date=date(2030, 1, 1))
    l2 = ln(st, p2, st.i1, Decimal("6.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert {(x.line_id, x.order_date) for x in result} == {
        (l1.id, date(2026, 3, 4)), (l2.id, date(2030, 1, 1)),
    }


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_f_13__later_workspace_supplier_is_no_supplier(db, st):
    """PII-F-13 — a later workspace's supplier is treated as no supplier.
    Rules: _fetch_history_lines R4a [BUG-2540]."""
    p1 = po(st, "PO-1", account_id=st.ac9.id)
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id}
    # Then 2
    assert result[0].account_id is None
    assert result[0].account_name is None


@pytest.mark.xfail(strict=True, reason=B2540)
def test_pii_f_14__earlier_workspace_supplier_is_no_supplier(db, st):
    """PII-F-14 — an earlier workspace's supplier is treated as no supplier.
    Rules: _fetch_history_lines R4a [BUG-2540]."""
    p1 = po(st, "PO-1", account_id=st.ac0.id)
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id}
    # Then 2
    assert result[0].account_id is None
    assert result[0].account_name is None


def test_pii_f_15__line_with_foreign_supplier_still_returned(db, st):
    """PII-F-15 — a line with a foreign supplier is still returned.
    Rules: _fetch_history_lines R1, R4a (regression part)."""
    p1 = po(st, "PO-1", account_id=st.ac9.id)
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert ids(result) == {l1.id}
    # Then 2
    assert result[0].unit_price == Decimal("5.00")


def test_pii_f_16__no_supplier_no_name_deleted_supplier_named(db, st):
    """PII-F-16 — no supplier gives no name; a deleted or inactive supplier is still named.
    Rules: _fetch_history_lines R4."""
    ad = _add(db, Account(workspace_id=st.w1.id, name="Gone Co", is_deleted=True, is_active=False))
    p1 = po(st, "PO-1")
    l1 = ln(st, p1, st.i1, Decimal("5.00"))
    p2 = po(st, "PO-2", account_id=ad.id)
    l2 = ln(st, p2, st.i1, Decimal("6.00"))
    result = fetch(db, st, [st.i1.id])
    # Then 1
    assert {(x.line_id, x.account_id, x.account_name) for x in result} == {
        (l1.id, None, None), (l2.id, ad.id, "Gone Co"),
    }


def test_pii_f_17__empty_item_ids_returns_empty_list(db, st):
    """PII-F-17 — empty item_ids returns an empty list.
    Rules: _fetch_history_lines R7."""
    p1 = po(st, "PO-1")
    ln(st, p1, st.i1, Decimal("5.00"))
    result = fetch(db, st, [])
    # Then 1
    assert result == []


# =========================================================================== #
# _pick_last_ordered
# =========================================================================== #

def test_pii_l_01__no_lines_gives_none():
    """PII-L-01 — no lines gives None.
    Rules: _pick_last_ordered R1."""
    result = svc._pick_last_ordered([])
    # Then 1
    assert result is None


def test_pii_l_02__latest_date_wins_over_higher_line_id():
    """PII-L-02 — the latest date wins over a higher line id.
    Rules: _pick_last_ordered R2."""
    a = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2))
    b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1))
    result = svc._pick_last_ordered([b, a])
    # Then 1
    assert result.purchase_order_id == 50
    assert result.order_date == date(2026, 3, 2)


def test_pii_l_03__date_tie_highest_line_id_wins():
    """PII-L-03 — on a date tie the highest line id wins.
    Rules: _pick_last_ordered R2."""
    a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2))
    b = HL(line_id=5, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=date(2026, 3, 2))
    result = svc._pick_last_ordered([b, a])
    # Then 1
    assert result.purchase_order_id == 10


def test_pii_l_04__unpriced_zero_supplierless_future_can_be_last():
    """PII-L-04 — an unpriced, zero-priced, supplier-less or future line can be last.
    Rules: _pick_last_ordered R2."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("0.00"), order_date=date(2030, 1, 1))
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    c = HL(line_id=3, purchase_order_id=30, unit_price=None, order_date=date(2029, 1, 1))
    result = (svc._pick_last_ordered([b, a]), svc._pick_last_ordered([b, c]))
    # Then 1
    assert result[0].purchase_order_id == 10
    assert result[0].unit_price == Decimal("0.00")
    # Then 2
    assert result[1].purchase_order_id == 30
    assert result[1].unit_price is None


def test_pii_l_05__no_dated_line_highest_line_id_wins():
    """PII-L-05 — with no dated line the highest line id wins.
    Rules: _pick_last_ordered R3."""
    a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=None)
    b = HL(line_id=5, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=None)
    result = svc._pick_last_ordered([b, a])
    # Then 1
    assert result.purchase_order_id == 10


def test_pii_l_06__undated_line_ignored_when_another_dated():
    """PII-L-06 — an undated line is ignored when another line has a date.
    Rules: _pick_last_ordered R3."""
    a = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("4.00"), order_date=None)
    b = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1))
    result = svc._pick_last_ordered([a, b])
    # Then 1
    assert result.purchase_order_id == 50


# =========================================================================== #
# _pick_min_price_ref
# =========================================================================== #

def test_pii_m_01__none_zero_negative_never_count():
    """PII-M-01 — None, zero and negative prices never count.
    Rules: _pick_min_price_ref R1."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=None, order_date=date(2026, 3, 1))
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1))
    c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("-1.00"), order_date=date(2026, 3, 1))
    d = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("0.01"), order_date=date(2026, 3, 1))
    result = svc._pick_min_price_ref([a, b, c, d])
    # Then 1
    assert result.purchase_order_id == 40
    assert result.unit_price == Decimal("0.01")


def test_pii_m_02__no_candidate_gives_none():
    """PII-M-02 — no candidate gives None.
    Rules: _pick_min_price_ref R3."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=None, order_date=date(2026, 3, 1))
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1))
    result = (svc._pick_min_price_ref([a, b]), svc._pick_min_price_ref([]))
    # Then 1
    assert result[0] is None
    # Then 2
    assert result[1] is None


def test_pii_m_03__both_window_bounds_inclusive():
    """PII-M-03 — both window bounds are inclusive.
    Rules: _pick_min_price_ref R2."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 2, 28))
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))
    c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("6.00"), order_date=date(2026, 3, 31))
    d = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("1.00"), order_date=date(2026, 4, 1))
    result = (
        svc._pick_min_price_ref([a, b, c, d], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)),
        svc._pick_min_price_ref([a, c, d], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)),
    )
    # Then 1
    assert result[0].purchase_order_id == 20
    # Then 2
    assert result[1].purchase_order_id == 30


def test_pii_m_04__undated_dropped_by_window_one_bound_no_window():
    """PII-M-04 — an undated line is dropped by a window; one bound alone applies no window.
    Rules: _pick_min_price_ref R2."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=None)
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 10))
    c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2025, 1, 1))
    result = (
        svc._pick_min_price_ref([a, b], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)),
        svc._pick_min_price_ref([b, c], from_date=date(2026, 3, 1)),
        svc._pick_min_price_ref([b, c], to_date=date(2024, 1, 1)),
    )
    # Then 1
    assert result[0].purchase_order_id == 20
    # Then 2
    assert result[1].purchase_order_id == 30
    # Then 3
    assert result[2].purchase_order_id == 30


def test_pii_m_05__cheapest_wins_over_earlier_lower_ids():
    """PII-M-05 — the cheapest wins over earlier and lower ids.
    Rules: _pick_min_price_ref R4."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("5.01"), order_date=date(2026, 1, 1))
    b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))
    result = svc._pick_min_price_ref([a, b])
    # Then 1
    assert result.purchase_order_id == 90
    assert str(result.unit_price) == "5.00"


def test_pii_m_06__price_tie_earliest_date_wins():
    """PII-M-06 — on a price tie the earliest date wins over a lower PO id.
    Rules: _pick_min_price_ref R4."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 2))
    b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))
    c = HL(line_id=8, purchase_order_id=80, unit_price=Decimal("5.00"), order_date=None)
    result = (svc._pick_min_price_ref([a, b]), svc._pick_min_price_ref([a, b, c]))
    # Then 1
    assert result[0].purchase_order_id == 90
    # Then 2
    assert result[1].purchase_order_id == 80


def test_pii_m_07__price_and_date_tie_lowest_po_id_wins():
    """PII-M-07 — on a price and date tie the lowest PO id wins over a lower line id.
    Rules: _pick_min_price_ref R4."""
    a = HL(line_id=1, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))
    b = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))
    result = svc._pick_min_price_ref([a, b])
    # Then 1
    assert result.purchase_order_id == 10


def test_pii_m_08__full_tie_within_po_lowest_line_id_wins():
    """PII-M-08 — on a full tie within one PO the lowest line id wins.
    Rules: _pick_min_price_ref R4."""
    a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    b = HL(line_id=4, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1),
           account_id=12, account_name="Beta")
    result = svc._pick_min_price_ref([a, b])
    # Then 1
    assert result.account_id == 12
    assert result.account_name == "Beta"


# =========================================================================== #
# _pick_avg_supplier_lowest
# =========================================================================== #

def test_pii_a_01__no_candidate_gives_none():
    """PII-A-01 — no candidate gives None.
    Rules: _pick_avg_supplier_lowest R1, R2."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1))
    b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    result = (svc._pick_avg_supplier_lowest([a, b]), svc._pick_avg_supplier_lowest([]))
    # Then 1
    assert result[0] is None
    # Then 2
    assert result[1] is None


def test_pii_a_02__supplierless_unpriced_zero_negative_never_compete():
    """PII-A-02 — supplier-less, unpriced, zero and negative lines never compete.
    Rules: _pick_avg_supplier_lowest R1."""
    n = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1))
    z = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1),
           account_id=21, account_name="Zero")
    g = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("-1.00"), order_date=date(2026, 3, 1),
           account_id=31, account_name="Neg")
    u = HL(line_id=4, purchase_order_id=40, unit_price=None, order_date=date(2026, 3, 1),
           account_id=41, account_name="None Co")
    a = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1),
           account_id=51, account_name="Acme")
    result = svc._pick_avg_supplier_lowest([n, z, g, u, a])
    # Then 1
    assert result.account_id == 51
    assert result.purchase_order_id == 50


def test_pii_a_03__average_weighted_by_quantity():
    """PII-A-03 — the average is weighted by quantity.
    Rules: _pick_avg_supplier_lowest R3, R4."""
    a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("10.00"))
    a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("10.00"), order_date=date(2026, 3, 2),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))
    b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("3.00"), order_date=date(2026, 3, 3),
           account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([b, a1, a2])
    # Then 1
    assert result.account_id == 11
    assert result.purchase_order_id == 10


def test_pii_a_04__averages_exact_not_rounded():
    """PII-A-04 — averages are exact, not rounded.
    Rules: _pick_avg_supplier_lowest R3, R4."""
    a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))
    a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("3.50"), order_date=date(2026, 3, 2),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("2.00"))
    b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("3.33"), order_date=date(2026, 3, 3),
           account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([a1, a2, b])
    # Then 1
    assert result.account_id == 12
    assert result.purchase_order_id == 30


def test_pii_a_05__quantity_zero_or_below_weighs_one():
    """PII-A-05 — a quantity of 0 or below weighs 1.
    Rules: _pick_avg_supplier_lowest R3."""
    a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("0.00"))
    a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("10.00"), order_date=date(2026, 3, 2),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))
    c1 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("10.20"), order_date=date(2026, 3, 1),
            account_id=13, account_name="Cobalt", quantity_ordered=Decimal("-5.00"))
    c2 = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("1.00"), order_date=date(2026, 3, 2),
            account_id=13, account_name="Cobalt", quantity_ordered=Decimal("1.00"))
    b = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("6.00"), order_date=date(2026, 3, 3),
           account_id=12, account_name="Beta")
    result = (svc._pick_avg_supplier_lowest([b, a1, a2]), svc._pick_avg_supplier_lowest([b, c1, c2]))
    # Then 1
    assert result[0].account_id == 11
    assert result[0].purchase_order_id == 10
    # Then 2
    assert result[1].account_id == 13
    assert result[1].purchase_order_id == 40


def test_pii_a_06__equal_average_more_distinct_orders_win():
    """PII-A-06 — on an equal average, more distinct orders win.
    Rules: _pick_avg_supplier_lowest R4."""
    b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    a1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
            account_id=12, account_name="Beta")
    a2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3),
            account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([b, a1, a2])
    # Then 1
    assert result.account_id == 12


def test_pii_a_07__orders_counted_distinct_not_lines():
    """PII-A-07 — orders are counted distinct, not lines.
    Rules: _pick_avg_supplier_lowest R4."""
    a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme")
    a2 = HL(line_id=2, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme")
    a3 = HL(line_id=3, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme")
    b1 = HL(line_id=4, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
            account_id=12, account_name="Beta")
    b2 = HL(line_id=5, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3),
            account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([a1, a2, a3, b1, b2])
    # Then 1
    assert result.account_id == 12


def test_pii_a_08__reference_is_winners_cheapest_never_zero():
    """PII-A-08 — the reference is the winner's cheapest line, never its zero line.
    Rules: _pick_avg_supplier_lowest R6."""
    a0 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("0.00"), order_date=date(2026, 3, 5),
            account_id=11, account_name="Acme")
    a1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("6.00"), order_date=date(2026, 3, 6),
            account_id=11, account_name="Acme")
    a2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("4.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme")
    b = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("9.00"), order_date=date(2026, 3, 1),
           account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([a0, a1, a2, b])
    # Then 1
    assert result.purchase_order_id == 30
    assert result.unit_price == Decimal("4.00")
    assert result.account_name == "Acme"


def test_pii_a_09__reference_ties_latest_date_po_id_line_id():
    """PII-A-09 — reference ties: latest date, then lowest PO id, then lowest line id.
    Rules: _pick_avg_supplier_lowest R6."""
    e = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    l = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2),
           account_id=11, account_name="Acme")
    p = HL(line_id=8, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2),
           account_id=11, account_name="Acme")
    q = HL(line_id=3, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2),
           account_id=11, account_name="ACME")
    n = HL(line_id=7, purchase_order_id=70, unit_price=Decimal("4.00"), order_date=None,
           account_id=11, account_name="Acme")
    result = (
        svc._pick_avg_supplier_lowest([e, l]),
        svc._pick_avg_supplier_lowest([l, p]),
        svc._pick_avg_supplier_lowest([p, q]),
        svc._pick_avg_supplier_lowest([n, e]),
    )
    # Then 1
    assert result[0].purchase_order_id == 90
    # Then 2
    assert result[1].purchase_order_id == 20
    # Then 3
    assert result[2].purchase_order_id == 20
    assert result[2].account_name == "ACME"
    # Then 4
    assert result[3].purchase_order_id == 10


@pytest.mark.xfail(strict=True, reason=B2543)
def test_pii_a_10__full_tie_goes_to_name_first_case_insensitive():
    """PII-A-10 — a full tie goes to the name first case-insensitively, not the first line.
    Rules: _pick_avg_supplier_lowest R5 [BUG-2543]."""
    b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Beta")
    a = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
           account_id=22, account_name="alpha")
    result = svc._pick_avg_supplier_lowest([b, a])
    # Then 1
    assert result.unit_price == Decimal("2.00")
    # Then 2
    assert result.account_id == 22
    assert result.account_name == "alpha"


@pytest.mark.xfail(strict=True, reason=B2543)
def test_pii_a_11__equal_names_lower_account_id_wins():
    """PII-A-11 — on equal names the lower account id wins, not the first line.
    Rules: _pick_avg_supplier_lowest R5 [BUG-2543]."""
    b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
           account_id=22, account_name="same")
    a = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
           account_id=11, account_name="SAME")
    result = svc._pick_avg_supplier_lowest([b, a])
    # Then 1
    assert result.unit_price == Decimal("2.00")
    # Then 2
    assert result.account_id == 11
    assert result.purchase_order_id == 20


def test_pii_a_12__cheaper_first_supplier_not_replaced_by_pricier_with_more_orders():
    """PII-A-12 — a cheaper supplier listed first is not replaced by a pricier one with more orders.
    Rules: _pick_avg_supplier_lowest R4."""
    a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    b1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
            account_id=12, account_name="Beta")
    b2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3),
            account_id=12, account_name="Beta")
    result = svc._pick_avg_supplier_lowest([a, b1, b2])
    # Then 1
    assert result.account_id == 11
    assert result.purchase_order_id == 10


def test_pii_a_13__equal_average_later_supplier_with_fewer_orders_does_not_replace():
    """PII-A-13 — on an equal average, a later supplier with fewer orders does not replace the first.
    Rules: _pick_avg_supplier_lowest R4."""
    b1 = HL(line_id=1, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
            account_id=12, account_name="Beta")
    b2 = HL(line_id=2, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2),
            account_id=12, account_name="Beta")
    a = HL(line_id=3, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3),
           account_id=11, account_name="Acme")
    result = svc._pick_avg_supplier_lowest([b1, b2, a])
    # Then 1
    assert result.account_id == 12


def test_pii_a_14__quantity_between_zero_and_one_weighs_its_quantity():
    """PII-A-14 — a quantity between 0 and 1 weighs its quantity, not 1.
    Rules: _pick_avg_supplier_lowest R3, R4."""
    a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("0.50"))
    a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2),
            account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))
    b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.75"), order_date=date(2026, 3, 3),
           account_id=12, account_name="Beta", quantity_ordered=Decimal("1.00"))
    result = svc._pick_avg_supplier_lowest([a1, a2, b])
    # Then 1
    assert result.account_id == 12
    assert result.purchase_order_id == 30


# --------------------------------------------------------------------------- #
# _HistoryLine
# --------------------------------------------------------------------------- #

def test_pii_dc_01__history_line_is_frozen():
    """PII-DC-01 — a history line is frozen.
    Rules: _HistoryLine (spec Not specified: frozen dataclass; Gap log G1)."""
    h = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1),
           account_id=11, account_name="Acme")
    # Then 1
    with pytest.raises(FrozenInstanceError):
        h.unit_price = Decimal("1.00")
    # Then 2
    assert h.unit_price == Decimal("2.00")
