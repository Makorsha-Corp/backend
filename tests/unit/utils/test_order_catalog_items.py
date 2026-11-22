"""Unit tests for app/utils/order_catalog_items.py.

Implements tests/unit/utils/order_catalog_items.cases.md (revision 4), one test
per case. Real Postgres session (`db` fixture); nothing is mocked (spec:
externals none, race simulations none, time not mocked).
"""
# ruff: noqa: FURB157  (prescribed by the cards: Decimal("...") literals)
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.utils.order_catalog_items import (
    assert_meets_minimum_order_quantities,
    assert_unique_catalog_item_ids,
    catalog_item_already_on_order_detail,
)
from tests.unit.factories import make_workspace

BUG_220 = "BUG-220: Empty catalog item name yields a nameless 409 message"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "UNKNOWN = 987654321, an id with no item in any workspace"
UNKNOWN = 987654321


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "F1, F2 = two factories in W1" (local builder; promote as make_factory later)
def mk_factory(db, ws, name):
    row = Factory(workspace_id=ws.id, name=name, abbreviation=name[:3].upper())
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1, "Factory One")


@pytest.fixture
def f2(db, w1):
    return mk_factory(db, w1, "Factory Two")


# Convention "Items" (catalog `items` rows, flushed so ids exist). EN (name "")
# is inserted directly, like a legacy/unguarded row.
def mk_item(db, ws, name, *, active=True):
    row = Item(
        workspace_id=ws.id,
        name=name,
        name_normalized=name.strip().lower(),
        unit="pcs",
        is_active=active,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def SR(db, w1):  # convention name
    return mk_item(db, w1, "Steel Rod")


@pytest.fixture
def OB(db, w1):
    return mk_item(db, w1, "Old Bolt", active=False)


@pytest.fixture
def A(db, w1):
    return mk_item(db, w1, "Alpha")


@pytest.fixture
def B(db, w1):
    return mk_item(db, w1, "Bravo")


@pytest.fixture
def SW(db, w2):
    return mk_item(db, w2, "Secret Widget")


@pytest.fixture
def EN(db, w1):
    return mk_item(db, w1, "")


# Convention "P(item, factory, min, for_sale=True, deleted=False, active=True)"
# in W1 unless stated (local builder; promote as make_product later).
def P(db, item, factory, min_qty, *, for_sale=True, deleted=False, active=True, ws=None):
    row = Product(
        workspace_id=(ws.id if ws is not None else item.workspace_id),
        item_id=item.id,
        factory_id=factory.id,
        qty=0,
        min_order_qty=min_qty,
        is_available_for_sale=for_sale,
        is_deleted=deleted,
        is_active=active,
    )
    db.add(row)
    db.flush()
    return row


# Convention "Lines": unique-check lines {"item_id": ...}; MOQ lines {"item_id", "qty"}
def uline(item_or_id):
    if item_or_id is None or isinstance(item_or_id, int):
        return {"item_id": item_or_id}
    return {"item_id": item_or_id.id}


def mline(item_or_id, qty):
    item_id = item_or_id if item_or_id is None or isinstance(item_or_id, int) else item_or_id.id
    return {"item_id": item_id, "qty": qty}


def get_item_id(e):
    return e["item_id"]


def get_quantity(e):
    return e["qty"]


# Convention "SENTINEL": accessor raises AssertionError("sentinel read") when it
# receives this object; the recording accessor logs every line it is passed.
SENTINEL = object()


class Recorder:
    def __init__(self):
        self.calls = []

    def item_id(self, e):
        self.calls.append(e)
        if e is SENTINEL:
            raise AssertionError("sentinel read")
        return e["item_id"]

    def quantity(self, e):
        self.calls.append(e)
        if e is SENTINEL:
            raise AssertionError("sentinel read")
        return e["qty"]


# Convention "DB unchanged": row counts and field values of items and products
# in W1/W2, read fresh from the database.
def snap(db, *wss):
    db.expire_all()
    ws_ids = [w.id for w in wss]
    items = db.execute(
        select(
            Item.id, Item.workspace_id, Item.name, Item.name_normalized, Item.unit,
            Item.sku, Item.description, Item.is_active, Item.item_type,
        ).where(Item.workspace_id.in_(ws_ids)).order_by(Item.id)
    ).all()
    products = db.execute(
        select(
            Product.id, Product.workspace_id, Product.item_id, Product.factory_id,
            Product.qty, Product.min_order_qty, Product.is_available_for_sale,
            Product.is_active, Product.is_deleted,
        ).where(Product.workspace_id.in_(ws_ids)).order_by(Product.id)
    ).all()
    return items, products


def reread_item(db, item_id):
    db.expire_all()
    return db.execute(select(Item).where(Item.id == item_id)).scalar_one()


def unique(db, ws, entries):
    return assert_unique_catalog_item_ids(db, ws.id, entries, get_item_id=get_item_id)


def moq(db, ws, factory, entries, **kw):
    kw.setdefault("get_item_id", get_item_id)
    kw.setdefault("get_quantity", get_quantity)
    return assert_meets_minimum_order_quantities(db, ws.id, factory.id, entries, **kw)


# --------------------------------------------------------------------------- #
# assert_unique_catalog_item_ids
# --------------------------------------------------------------------------- #


def test_oci_u_01__empty_list_passes(db, w1):
    """OCI-U-01 — an empty list passes.
    Rules: assert_unique_catalog_item_ids R1."""
    assert assert_unique_catalog_item_ids(db, w1.id, [], get_item_id=get_item_id) is None


def test_oci_u_02__empty_generator_passes(db, w1):
    """OCI-U-02 — an empty generator passes.
    Rules: assert_unique_catalog_item_ids R1."""
    assert unique(db, w1, (x for x in [])) is None


def test_oci_u_03__free_text_lines_never_duplicates(db, w1):
    """OCI-U-03 — three free-text lines pass.
    Rules: assert_unique_catalog_item_ids R2."""
    assert unique(db, w1, [{"item_id": None}] * 3) is None


def test_oci_u_04__free_text_mixed_with_distinct_ids(db, w1):
    """OCI-U-04 — None, 101, None, 102, None pass.
    Rules: assert_unique_catalog_item_ids R2, R3."""
    assert unique(db, w1, [uline(i) for i in [None, 101, None, 102, None]]) is None


def test_oci_u_05__zero_id_is_deduplicated(db, w1):
    """OCI-U-05 — item id 0 is a real id: [0, 0] raises 409 "Item #0 ...".
    Rules: assert_unique_catalog_item_ids R2, R5, R6."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [{"item_id": 0}, {"item_id": 0}])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Item #0 appears more than once on this order"


def test_oci_u_06__fifty_distinct_ids_pass_each_read_once(db, w1):
    """OCI-U-06 — generator of 50 distinct ids passes; accessor called 50 times, each id once.
    Rules: assert_unique_catalog_item_ids R3."""
    rec = Recorder()
    gen = ({"item_id": i} for i in range(1, 51))
    assert assert_unique_catalog_item_ids(db, w1.id, gen, get_item_id=rec.item_id) is None
    assert len(rec.calls) == 50
    assert sorted(c["item_id"] for c in rec.calls) == list(range(1, 51))


def test_oci_u_07__duplicate_raises_409_with_item_name(db, w1, w2, SR):
    """OCI-U-07 — [SR, SR] raises 409 "Steel Rod appears more than once on this order"; DB unchanged.
    Rules: assert_unique_catalog_item_ids R4, R5, R6; Errors row."""
    before = snap(db, w1, w2)
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(SR), uline(SR)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Steel Rod appears more than once on this order"
    assert snap(db, w1, w2) == before
    row = reread_item(db, SR.id)
    assert row.name == "Steel Rod"
    assert row.is_active is True


def test_oci_u_08__first_second_occurrence_wins(db, w1, A, B):
    """OCI-U-08 — [A, B, B, A] names Bravo (its second occurrence comes first).
    Rules: assert_unique_catalog_item_ids R4."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(A), uline(B), uline(B), uline(A)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Bravo appears more than once on this order"


def test_oci_u_09__lines_after_duplicate_not_examined(db, w1, A):
    """OCI-U-09 — generator A, A, SENTINEL raises 409 before SENTINEL is read.
    Rules: assert_unique_catalog_item_ids R4."""
    rec = Recorder()
    a1, a2 = uline(A), uline(A)
    gen = (e for e in [a1, a2, SENTINEL])
    with pytest.raises(HTTPException) as exc:
        assert_unique_catalog_item_ids(db, w1.id, gen, get_item_id=rec.item_id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Alpha appears more than once on this order"
    assert len(rec.calls) == 2
    assert rec.calls[0] is a1 and rec.calls[1] is a2


def test_oci_u_10__inactive_item_name_used(db, w1, OB):
    """OCI-U-10 — [OB, OB] (inactive) names "Old Bolt".
    Rules: assert_unique_catalog_item_ids R5."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(OB), uline(OB)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Old Bolt appears more than once on this order"


def test_oci_u_11__unknown_id_falls_back(db, w1):
    """OCI-U-11 — [UNKNOWN, UNKNOWN] names "Item #987654321".
    Rules: assert_unique_catalog_item_ids R5."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(UNKNOWN), uline(UNKNOWN)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Item #987654321 appears more than once on this order"


def test_oci_u_12__other_workspace_name_not_revealed(db, w1, SW):
    """OCI-U-12 — W1 call with W2's item id falls back to Item #<id>, never "Secret Widget".
    Rules: assert_unique_catalog_item_ids R5."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(SW.id), uline(SW.id)])
    assert exc.value.status_code == 409
    assert exc.value.detail == f"Item #{SW.id} appears more than once on this order"
    assert "Secret Widget" not in exc.value.detail


def test_oci_u_13__own_workspace_name_used(db, w2, SW):
    """OCI-U-13 — W2 call with W2's item names "Secret Widget".
    Rules: assert_unique_catalog_item_ids R5."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w2, [uline(SW.id), uline(SW.id)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Secret Widget appears more than once on this order"


def test_oci_u_14__free_text_between_does_not_break_detection(db, w1, SR):
    """OCI-U-14 — [SR, None, SR] raises 409 naming Steel Rod.
    Rules: assert_unique_catalog_item_ids R2, R4."""
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(SR), uline(None), uline(SR)])
    assert exc.value.status_code == 409
    assert exc.value.detail == "Steel Rod appears more than once on this order"


@pytest.mark.xfail(strict=True, reason=BUG_220)
def test_oci_u_15__empty_name_falls_back_to_item_id(db, w1, w2, EN):
    """OCI-U-15 — [EN, EN] (empty name) detail is "Item #<id> appears ..."; DB unchanged.
    Rules: assert_unique_catalog_item_ids R5a [BUG-220], R6."""
    before = snap(db, w1, w2)
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(EN), uline(EN)])
    assert exc.value.status_code == 409
    assert exc.value.detail == f"Item #{EN.id} appears more than once on this order"
    assert not exc.value.detail.startswith(" ")
    assert snap(db, w1, w2) == before
    assert reread_item(db, EN.id).name == ""


def test_oci_u_16__empty_name_still_raises_409(db, w1, w2, EN):
    """OCI-U-16 — [EN, EN] still raises 409 with the fixed suffix; DB unchanged (BUG-220 independent).
    Rules: assert_unique_catalog_item_ids R4, R5a, R6."""
    before = snap(db, w1, w2)
    with pytest.raises(HTTPException) as exc:
        unique(db, w1, [uline(EN), uline(EN)])
    assert exc.value.status_code == 409
    assert exc.value.detail.endswith(" appears more than once on this order")
    assert snap(db, w1, w2) == before
    assert reread_item(db, EN.id).name == ""


# --------------------------------------------------------------------------- #
# catalog_item_already_on_order_detail
# --------------------------------------------------------------------------- #


def test_oci_d_01__item_name_used(db, w1, w2, SR):
    """OCI-D-01 — returns "Steel Rod is already on this order"; DB unchanged.
    Rules: catalog_item_already_on_order_detail R1."""
    before = snap(db, w1, w2)
    out = catalog_item_already_on_order_detail(db, item_id=SR.id, workspace_id=w1.id)
    assert out == "Steel Rod is already on this order"
    assert snap(db, w1, w2) == before


def test_oci_d_02__inactive_item_name_used(db, w1, OB):
    """OCI-D-02 — inactive item: "Old Bolt is already on this order".
    Rules: catalog_item_already_on_order_detail R1."""
    out = catalog_item_already_on_order_detail(db, item_id=OB.id, workspace_id=w1.id)
    assert out == "Old Bolt is already on this order"


def test_oci_d_03__unknown_id_falls_back(db, w1):
    """OCI-D-03 — unknown id: "Item #987654321 is already on this order", no exception.
    Rules: catalog_item_already_on_order_detail R2."""
    out = catalog_item_already_on_order_detail(db, item_id=UNKNOWN, workspace_id=w1.id)
    assert out == "Item #987654321 is already on this order"


def test_oci_d_04__other_workspace_name_not_revealed(db, w1, SW):
    """OCI-D-04 — W2 item looked up in W1: Item #<id>, "Secret Widget" not revealed.
    Rules: catalog_item_already_on_order_detail R2."""
    out = catalog_item_already_on_order_detail(db, item_id=SW.id, workspace_id=w1.id)
    assert out == f"Item #{SW.id} is already on this order"
    assert "Secret Widget" not in out


def test_oci_d_05__own_workspace_name_used(db, w2, SW):
    """OCI-D-05 — W2 item looked up in W2: "Secret Widget is already on this order".
    Rules: catalog_item_already_on_order_detail R1."""
    out = catalog_item_already_on_order_detail(db, item_id=SW.id, workspace_id=w2.id)
    assert out == "Secret Widget is already on this order"


@pytest.mark.xfail(strict=True, reason=BUG_220)
def test_oci_d_06__empty_name_falls_back_to_item_id(db, w1, w2, EN):
    """OCI-D-06 — empty name: "Item #<id> is already on this order"; DB unchanged.
    Rules: catalog_item_already_on_order_detail R3 [BUG-220]."""
    before = snap(db, w1, w2)
    out = catalog_item_already_on_order_detail(db, item_id=EN.id, workspace_id=w1.id)
    assert out == f"Item #{EN.id} is already on this order"
    assert not out.startswith(" ")
    assert snap(db, w1, w2) == before


def test_oci_d_07__empty_name_still_returns_message(db, w1, EN):
    """OCI-D-07 — empty name: returns a str ending with " is already on this order" (BUG-220 independent).
    Rules: catalog_item_already_on_order_detail R1, R3."""
    out = catalog_item_already_on_order_detail(db, item_id=EN.id, workspace_id=w1.id)
    assert isinstance(out, str)
    assert out.endswith(" is already on this order")


# --------------------------------------------------------------------------- #
# assert_meets_minimum_order_quantities
# --------------------------------------------------------------------------- #


def test_oci_m_01__empty_list_passes(db, w1, f1):
    """OCI-M-01 — empty entries pass.
    Rules: assert_meets_minimum_order_quantities R1."""
    assert moq(db, w1, f1, []) is None


def test_oci_m_02__free_text_quantity_never_read(db, w1, f1):
    """OCI-M-02 — free-text lines pass and get_quantity is never called.
    Rules: assert_meets_minimum_order_quantities R2."""
    calls = []

    def no_quantity(e):
        calls.append(e)
        raise AssertionError("get_quantity must not be called")

    entries = [{"item_id": None, "qty": Decimal("-3")}, {"item_id": None, "qty": Decimal("0")}]
    assert moq(db, w1, f1, entries, get_quantity=no_quantity) is None
    assert calls == []


def test_oci_m_03__below_min_raises_422(db, w1, w2, f1, SR):
    """OCI-M-03 — 4.5 against min 5 raises 422 with exact detail; DB unchanged.
    Rules: assert_meets_minimum_order_quantities R3, R6, R7; Errors row."""
    P(db, SR, f1, 5)
    before = snap(db, w1, w2)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("4.5"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 4.5)"
    assert snap(db, w1, w2) == before


@pytest.mark.parametrize(
    "qty",
    [
        pytest.param(Decimal("5"), id="OCI-M-04"),
        pytest.param(Decimal("6"), id="OCI-M-05"),
    ],
)
def test_oci_m_04_05__at_or_above_min_passes(db, w1, f1, SR, qty):
    """OCI-M-04 / OCI-M-05 — quantity equal to (5) or above (6) min 5 passes.
    Rules: assert_meets_minimum_order_quantities R6."""
    P(db, SR, f1, 5)
    assert moq(db, w1, f1, [mline(SR, qty)]) is None


def test_oci_m_06__just_below_min_raises(db, w1, f1, SR):
    """OCI-M-06 — 4.99 against min 5 raises 422.
    Rules: assert_meets_minimum_order_quantities R6."""
    P(db, SR, f1, 5)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("4.99"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 4.99)"


def test_oci_m_07__no_product_passes(db, w1, f1, SR):
    """OCI-M-07 — no product for SR anywhere: passes.
    Rules: assert_meets_minimum_order_quantities R4."""
    assert moq(db, w1, f1, [mline(SR, Decimal("1"))]) is None


def test_oci_m_08__product_for_other_factory_ignored(db, w1, f1, f2, SR):
    """OCI-M-08 — product only for F2; call with F1 passes.
    Rules: assert_meets_minimum_order_quantities R3, R4."""
    P(db, SR, f2, 5)
    assert moq(db, w1, f1, [mline(SR, Decimal("1"))]) is None


def test_oci_m_09__product_in_other_workspace_ignored(db, w1, w2, f1, SR):
    """OCI-M-09 — product in W1; call with W2 passes.
    Rules: assert_meets_minimum_order_quantities R3, R4."""
    P(db, SR, f1, 5)
    assert moq(db, w2, f1, [mline(SR, Decimal("1"))]) is None


def test_oci_m_10__not_for_sale_product_ignored(db, w1, f1, SR):
    """OCI-M-10 — only a not-for-sale product: passes.
    Rules: assert_meets_minimum_order_quantities R3, R4."""
    P(db, SR, f1, 5, for_sale=False)
    assert moq(db, w1, f1, [mline(SR, Decimal("1"))]) is None


def test_oci_m_11__soft_deleted_product_ignored(db, w1, f1, SR):
    """OCI-M-11 — only a soft-deleted product: passes.
    Rules: assert_meets_minimum_order_quantities R3, R4."""
    P(db, SR, f1, 5, deleted=True)
    assert moq(db, w1, f1, [mline(SR, Decimal("1"))]) is None


def test_oci_m_12__inactive_product_still_enforced(db, w1, f1, SR):
    """OCI-M-12 — is_active=False product is still used: 422.
    Rules: assert_meets_minimum_order_quantities R3."""
    P(db, SR, f1, 5, active=False)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("1"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 1)"


def test_oci_m_13__not_for_sale_min_not_used(db, w1, f1, SR):
    """OCI-M-13 — not-for-sale min 100 and for-sale min 5; 10 passes.
    Rules: assert_meets_minimum_order_quantities R3."""
    P(db, SR, f1, 100, for_sale=False)
    P(db, SR, f1, 5, for_sale=True)
    assert moq(db, w1, f1, [mline(SR, Decimal("10"))]) is None


def test_oci_m_14__for_sale_min_used_in_message(db, w1, f1, SR):
    """OCI-M-14 — same setup as M-13; 4 raises 422 naming min 5 (for-sale product), not 100.
    Rules: assert_meets_minimum_order_quantities R3, R7."""
    P(db, SR, f1, 100, for_sale=False)
    P(db, SR, f1, 5, for_sale=True)  # p = the for-sale product (min 5)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("4"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 4)"


def test_oci_m_15__null_min_means_no_minimum(db, w1, f1, SR):
    """OCI-M-15 — min None: quantity 0 passes.
    Rules: assert_meets_minimum_order_quantities R5."""
    P(db, SR, f1, None)
    assert moq(db, w1, f1, [mline(SR, Decimal("0"))]) is None


def test_oci_m_16__zero_min_means_no_minimum(db, w1, f1, SR):
    """OCI-M-16 — min 0: quantity -1 passes.
    Rules: assert_meets_minimum_order_quantities R5."""
    P(db, SR, f1, 0)
    assert moq(db, w1, f1, [mline(SR, Decimal("-1"))]) is None


def test_oci_m_17__min_one_enforced(db, w1, f1, SR):
    """OCI-M-17 — min 1: quantity 0 raises 422.
    Rules: assert_meets_minimum_order_quantities R5, R6."""
    P(db, SR, f1, 1)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("0"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 1 (requested 0)"


def test_oci_m_18__empty_item_name_falls_back(db, w1, f1, EN):
    """OCI-M-18 — empty item name: detail names "Item #<id>".
    Rules: assert_meets_minimum_order_quantities R7."""
    P(db, EN, f1, 5)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(EN, Decimal("1"))])
    assert exc.value.status_code == 422
    assert exc.value.detail == f"Minimum order quantity for Item #{EN.id} is 5 (requested 1)"


def test_oci_m_19__quantity_rendered_with_str(db, w1, f1, SR):
    """OCI-M-19 — Decimal("4.50") renders as "4.50" (trailing zero kept).
    Rules: assert_meets_minimum_order_quantities R7."""
    P(db, SR, f1, 5)
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, [mline(SR, Decimal("4.50"))])
    assert exc.value.status_code == 422
    assert exc.value.detail.endswith("(requested 4.50)")
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 4.50)"


def test_oci_m_20__first_failing_line_raises(db, w1, f1, A, B):
    """OCI-M-20 — [A 6, B 1, A 1]: the B line (first failure) is reported.
    Rules: assert_meets_minimum_order_quantities R8."""
    P(db, A, f1, 5)
    P(db, B, f1, 10)
    gen = (e for e in [mline(A, Decimal("6")), mline(B, Decimal("1")), mline(A, Decimal("1"))])
    with pytest.raises(HTTPException) as exc:
        moq(db, w1, f1, gen)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Bravo is 10 (requested 1)"


def test_oci_m_21__lines_after_failure_not_examined(db, w1, f1, A):
    """OCI-M-21 — generator A(1), SENTINEL: 422 raised before SENTINEL is read.
    Rules: assert_meets_minimum_order_quantities R8."""
    P(db, A, f1, 5)
    rec = Recorder()
    a_line = mline(A, Decimal("1"))
    gen = (e for e in [a_line, SENTINEL])
    with pytest.raises(HTTPException) as exc:
        assert_meets_minimum_order_quantities(
            db, w1.id, f1.id, gen, get_item_id=rec.item_id, get_quantity=rec.quantity
        )
    assert exc.value.status_code == 422
    assert rec.calls
    assert all(c is a_line for c in rec.calls)


def test_oci_m_22__none_quantity_raises_type_error(db, w1, w2, f1, SR):
    """OCI-M-22 — quantity None against positive min raises TypeError, not HTTPException; DB unchanged.
    Rules: assert_meets_minimum_order_quantities R9."""
    P(db, SR, f1, 5)
    before = snap(db, w1, w2)
    with pytest.raises(TypeError):
        moq(db, w1, f1, [{"item_id": SR.id, "qty": None}])
    assert snap(db, w1, w2) == before


def test_oci_m_23__free_text_before_catalog_line_is_skipped_not_stop(db, w1, w2, f1, SR):
    """OCI-M-23 — free-text line before a catalog line is skipped; the SR line after it still raises 422.
    Rules: assert_meets_minimum_order_quantities R2, R6, R8."""
    P(db, SR, f1, 5)
    before = snap(db, w1, w2)
    free_line = {"item_id": None, "qty": Decimal("1")}
    sr_line = mline(SR, Decimal("1"))
    quantity_calls = []

    def recording_quantity(e):
        quantity_calls.append(e)
        return e["qty"]

    gen = (e for e in [free_line, sr_line])
    with pytest.raises(HTTPException) as exc:
        assert_meets_minimum_order_quantities(
            db, w1.id, f1.id, gen, get_item_id=get_item_id, get_quantity=recording_quantity
        )
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Steel Rod is 5 (requested 1)"
    assert len(quantity_calls) == 1 and quantity_calls[0] is sr_line
    assert snap(db, w1, w2) == before


def test_oci_m_24__other_items_product_not_applied(db, w1, w2, f1, A, B):
    """OCI-M-24 — only A has a product in F1 (min 5); a B line of qty 1 passes; DB unchanged.
    Rules: assert_meets_minimum_order_quantities R3, R4."""
    P(db, A, f1, 5)  # no product for B anywhere
    before = snap(db, w1, w2)
    assert moq(db, w1, f1, [{"item_id": B.id, "qty": Decimal("1")}]) is None
    assert snap(db, w1, w2) == before
