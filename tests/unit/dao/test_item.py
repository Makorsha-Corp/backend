"""Unit tests for app/dao/item.py.

Implements tests/unit/dao/item.cases.md (revision 3) one test per case.
Real Postgres session (`db` fixture), nothing mocked (spec: no externals).
"""
# ruff: noqa: SIM117  (prescribed by the cards: nested with)
import itertools

import psycopg2.errors
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.engine import Row
from sqlalchemy.exc import DataError

from app.dao.item import item_dao
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.utils.item_name_normalize import normalize_item_name
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

_tag_seq = itertools.count(1)


# Convention "W1, W2 = two existing workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "W404 = an integer that is no workspace's id (max workspace id + 1000)"
@pytest.fixture
def w404(db, w1, w2):
    from app.models.workspace import Workspace

    return (db.scalar(select(func.max(Workspace.id))) or 0) + 1000


# Convention "Item shorthand": A "Zeta Rod" (pcs) -> active item, sku/desc NULL,
# name_normalized = normalized name unless nn= is given. One insert + flush per
# item, so ids ascend in insertion order.
def mk(db, ws, name, unit="pcs", *, sku=None, desc=None, nn=None, deleted=False):
    row = Item(
        workspace_id=ws.id,
        name=name,
        name_normalized=normalize_item_name(name) if nn is None else nn,
        unit=unit,
        sku=sku,
        description=desc,
        is_active=not deleted,
    )
    db.add(row)
    db.flush()
    return row


# Convention "Tags": T1 "Galvanized" (W1) -> ItemTag with unique tag_code;
# Tdel -> is_active=False.
def mktag(db, ws, name, *, active=True):
    row = ItemTag(
        workspace_id=ws.id, name=name, tag_code=f"T{next(_tag_seq)}", is_active=active
    )
    db.add(row)
    db.flush()
    return row


# Convention "A tagged T1" -> assignment in A's workspace unless stated.
def tag(db, item, t, *, ws_id=None):
    row = ItemTagAssignment(
        workspace_id=item.workspace_id if ws_id is None else ws_id,
        item_id=item.id,
        tag_id=t.id,
    )
    db.add(row)
    db.flush()
    return row


# Convention "UNKNOWN_TAG = max tag id + 1000"
def unknown_tag(db):
    return (db.scalar(select(func.max(ItemTag.id))) or 0) + 1000


# Convention "Generated names": N(1)="aaa", N(2)="aab", ..., N(27)="aba"
def N(k):
    i = k - 1
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[i // 676] + letters[(i // 26) % 26] + letters[i % 26]


# Convention "Actions": list(...) with workspace_id=W1, limit=100
def lst(db, w1, **kw):
    kw.setdefault("limit", 100)
    return item_dao.list_active_items_filtered(db, workspace_id=w1.id, **kw)


def ids(rows):
    return [r.id for r in rows]


# AF section: compared as sorted ids
def af_ids(db, w1, **kw):
    return sorted(ids(lst(db, w1, **kw)))


def srt(*items):
    return sorted(i.id for i in items)


# Convention "Actions": count(...) with workspace_id=W1
def cnt(db, w1, **kw):
    return item_dao.count_active_items_filtered(db, workspace_id=w1.id, **kw)


# Convention "Actions": units(ws)
def units(db, ws_id):
    return item_dao.distinct_units_in_workspace(db, workspace_id=ws_id)


# Convention "Actions": similar(name, ...) with workspace_id=W1, default limit 5
def similar(db, w1, name, **kw):
    return item_dao.find_similar_by_name_in_workspace(db, workspace_id=w1.id, name=name, **kw)


def pairs(rows):
    return [(r[0].id, r[1]) for r in rows]


def approx(x):
    return pytest.approx(x, abs=1e-4)


# Convention "Read-only check (session clean)"
def assert_session_clean(db):
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# Convention "SQL statement counter": before_cursor_execute listener on the engine
class StatementCounter:
    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def _on(self, *args, **kwargs):
        self.count += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False


# Convention "Trigram preconditions"
def sim(db, a, b):
    return db.execute(text("SELECT similarity(:a, :b)"), {"a": a, "b": b}).scalar()


# Convention "Database-error cases": snapshot / re-read of W1 items
def snapshot(db, w1):
    db.expire_all()
    rows = db.scalars(select(Item).where(Item.workspace_id == w1.id).order_by(Item.id)).all()
    return [(r.id, r.name, r.unit, r.is_active) for r in rows]


# =========================================================================== #
# _apply_item_catalog_filters (exercised through list_active_items_filtered)
# =========================================================================== #


def test_item_af_01__no_filters_returns_all_active(db, w1):
    """ITEM-AF-01 — with no search/unit/tag_ids every active item of W1 is returned.
    Rules: _apply_item_catalog_filters R3."""
    a = mk(db, w1, "Zeta Rod", "pcs")
    b = mk(db, w1, "Plain Bar", "kg")
    c = mk(db, w1, "Hex Bolt", "box")
    assert af_ids(db, w1) == srt(a, b, c)
    assert_session_clean(db)


def test_item_af_02__other_workspace_item_absent(db, w1, w2):
    """ITEM-AF-02 — an identical item in W2 is not returned for W1.
    Rules: _apply_item_catalog_filters R1."""
    a = mk(db, w1, "Zeta Rod")
    x = mk(db, w2, "Zeta Rod")
    result = af_ids(db, w1)
    assert result == srt(a)
    assert x.id not in result


def test_item_af_03__search_equal_to_other_workspace_id_no_match(db, w1, w2):
    """ITEM-AF-03 — searching another workspace's item id does not return it.
    Rules: _apply_item_catalog_filters R1, R11."""
    mk(db, w1, "Hex Bolt")
    x = mk(db, w2, "Hex Bolt")
    result = af_ids(db, w1, search=str(x.id))
    assert result == []
    assert x.id not in result


def test_item_af_04__tag_filter_other_workspace_tag(db, w1, w2):
    """ITEM-AF-04 — a W2 tag id used as W1 filter returns nothing.
    Rules: _apply_item_catalog_filters R1, R7."""
    t2 = mktag(db, w2, "Galvanized")
    x = mk(db, w2, "Hex Bolt")
    tag(db, x, t2)
    mk(db, w1, "Hex Bolt")
    assert af_ids(db, w1, tag_ids=[t2.id]) == []


def test_item_af_05__deleted_item_absent(db, w1):
    """ITEM-AF-05 — a soft-deleted item is not listed.
    Rules: _apply_item_catalog_filters R2."""
    a = mk(db, w1, "Zeta Rod")
    d = mk(db, w1, "Zeta Rod", deleted=True)
    result = af_ids(db, w1)
    assert result == srt(a)
    assert d.id not in result


def test_item_af_06__deleted_item_absent_from_search(db, w1):
    """ITEM-AF-06 — a soft-deleted item does not match a search.
    Rules: _apply_item_catalog_filters R2."""
    a = mk(db, w1, "Zeta Rod")
    d = mk(db, w1, "Zeta Rod", deleted=True)
    result = af_ids(db, w1, search="zeta")
    assert result == srt(a)
    assert d.id not in result


def test_item_af_07__deleted_item_absent_from_tag_filter(db, w1):
    """ITEM-AF-07 — a soft-deleted tagged item does not match the tag filter.
    Rules: _apply_item_catalog_filters R2."""
    t1 = mktag(db, w1, "Galvanized")
    d = mk(db, w1, "Hex Bolt", deleted=True)
    tag(db, d, t1)
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, tag_ids=[t1.id]) == []


def test_item_af_08__empty_search_is_no_search(db, w1):
    """ITEM-AF-08 — search="" applies no search.
    Rules: _apply_item_catalog_filters R3."""
    a = mk(db, w1, "Zeta Rod")
    b = mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="") == srt(a, b)


def test_item_af_09__whitespace_search_is_no_search(db, w1):
    """ITEM-AF-09 — whitespace-only search applies no search.
    Rules: _apply_item_catalog_filters R3, R9."""
    a = mk(db, w1, "Zeta Rod")
    b = mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="   ") == srt(a, b)


def test_item_af_10__unit_filter_exact_value(db, w1):
    """ITEM-AF-10 — unit="kg" returns the kg item, not pcs or kgs.
    Rules: _apply_item_catalog_filters R4."""
    a = mk(db, w1, "Rod", "kg")
    b = mk(db, w1, "Bar", "pcs")
    c = mk(db, w1, "Sack", "kgs")
    result = af_ids(db, w1, unit="kg")
    assert result == srt(a)
    assert b.id not in result and c.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_af_11__unit_filter_case_insensitive(db, w1):
    """ITEM-AF-11 — unit="kg" matches kg, Kg, KG but not kgs or pcs.
    Rules: _apply_item_catalog_filters R4 [BUG-017]."""
    a = mk(db, w1, "Rod", "kg")
    b = mk(db, w1, "Bar", "Kg")
    c = mk(db, w1, "Pin", "KG")
    d = mk(db, w1, "Sack", "kgs")
    e = mk(db, w1, "Nut", "pcs")
    result = af_ids(db, w1, unit="kg")
    assert result == srt(a, b, c)
    assert d.id not in result and e.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_af_12__unit_filter_value_trimmed(db, w1):
    """ITEM-AF-12 — unit="kg " behaves like unit="kg".
    Rules: _apply_item_catalog_filters R4 [BUG-017]."""
    a = mk(db, w1, "Rod", "kg")
    mk(db, w1, "Bar", "pcs")
    assert af_ids(db, w1, unit="kg ") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_af_13__whitespace_unit_is_no_filter(db, w1):
    """ITEM-AF-13 — whitespace-only unit applies no unit filter.
    Rules: _apply_item_catalog_filters R4 [BUG-017]."""
    a = mk(db, w1, "Rod", "kg")
    b = mk(db, w1, "Bar", "pcs")
    assert af_ids(db, w1, unit="   ") == srt(a, b)


def test_item_af_14__empty_unit_is_no_filter(db, w1):
    """ITEM-AF-14 — unit="" applies no unit filter.
    Rules: _apply_item_catalog_filters R4."""
    a = mk(db, w1, "Rod", "kg")
    b = mk(db, w1, "Bar", "pcs")
    assert af_ids(db, w1, unit="") == srt(a, b)


def _af15_setup(db, w1):
    t1 = mktag(db, w1, "Galvanized")
    t2 = mktag(db, w1, "Painted")
    t3 = mktag(db, w1, "Coated")
    a = mk(db, w1, "Rod")
    tag(db, a, t1)
    b = mk(db, w1, "Bar")
    tag(db, b, t2)
    c = mk(db, w1, "Pin")
    tag(db, c, t3)
    d = mk(db, w1, "Nut")
    return t1, t2, t3, a, b, c, d


def test_item_af_15__tag_filter_any_of(db, w1):
    """ITEM-AF-15 — tag_ids=[T1, T2] returns items with either tag.
    Rules: _apply_item_catalog_filters R5."""
    t1, t2, _t3, a, b, c, d = _af15_setup(db, w1)
    result = af_ids(db, w1, tag_ids=[t1.id, t2.id])
    assert result == srt(a, b)
    assert c.id not in result and d.id not in result


def test_item_af_16__empty_tag_ids_is_no_filter(db, w1):
    """ITEM-AF-16 — tag_ids=[] applies no tag filter.
    Rules: _apply_item_catalog_filters R5."""
    _t1, _t2, _t3, a, b, c, d = _af15_setup(db, w1)
    assert af_ids(db, w1, tag_ids=[]) == srt(a, b, c, d)


@pytest.mark.xfail(strict=True, reason="BUG-014: Filtering by a deleted tag still returns items")
def test_item_af_17__deleted_tag_filter_matches_nothing(db, w1):
    """ITEM-AF-17 — filtering only by a deleted tag returns nothing.
    Rules: _apply_item_catalog_filters R6 [BUG-014]."""
    tdel = mktag(db, w1, "Obsolete", active=False)
    a = mk(db, w1, "Rod")
    tag(db, a, tdel)
    mk(db, w1, "Bar")
    assert af_ids(db, w1, tag_ids=[tdel.id]) == []


@pytest.mark.xfail(strict=True, reason="BUG-014: Filtering by a deleted tag still returns items")
def test_item_af_18__deleted_and_active_tag_filter(db, w1):
    """ITEM-AF-18 — with [Tdel, T1] only the item with the active tag is returned, once.
    Rules: _apply_item_catalog_filters R6 [BUG-014]."""
    tdel = mktag(db, w1, "Obsolete", active=False)
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Rod")
    tag(db, a, tdel)
    b = mk(db, w1, "Bar")
    tag(db, b, tdel)
    tag(db, b, t1)
    result = af_ids(db, w1, tag_ids=[tdel.id, t1.id])
    assert result == srt(b)
    assert a.id not in result


def test_item_af_19__assignment_in_other_workspace_ignored(db, w1, w2):
    """ITEM-AF-19 — an assignment whose workspace is W2 does not match a W1 tag filter.
    Rules: _apply_item_catalog_filters R7."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Rod")
    tag(db, a, t1, ws_id=w2.id)
    assert af_ids(db, w1, tag_ids=[t1.id]) == []


def test_item_af_20__unknown_tag_matches_nothing(db, w1):
    """ITEM-AF-20 — an unknown tag id alone returns nothing.
    Rules: _apply_item_catalog_filters R7."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Rod")
    tag(db, a, t1)
    assert af_ids(db, w1, tag_ids=[unknown_tag(db)]) == []


def test_item_af_21__unknown_tag_with_known_tag(db, w1):
    """ITEM-AF-21 — [T1, UNKNOWN_TAG] returns the T1 item.
    Rules: _apply_item_catalog_filters R7, R5."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Rod")
    tag(db, a, t1)
    mk(db, w1, "Bar")
    assert af_ids(db, w1, tag_ids=[t1.id, unknown_tag(db)]) == srt(a)


def test_item_af_22__search_fields_case_insensitive(db, w1):
    """ITEM-AF-22 — search matches name/description/sku/unit case-insensitively; NULL fields ok.
    Rules: _apply_item_catalog_filters R9, R10, R13."""
    a = mk(db, w1, "Zeta Rod", "pcs")
    b = mk(db, w1, "Plain Bar", "pcs", desc="made of zeta alloy")
    c = mk(db, w1, "Hex Bolt", "pcs", sku="ZETA-AB")
    d = mk(db, w1, "Rope", "zetaroll")
    e = mk(db, w1, "Plain Nut", "pcs", sku="PN-AB", desc="steel")
    f = mk(db, w1, "Zeta Cap", "pcs", deleted=True)
    result = af_ids(db, w1, search="ZeTa")
    assert result == srt(a, b, c, d)
    assert e.id not in result and f.id not in result


def test_item_af_23__search_trimmed(db, w1):
    """ITEM-AF-23 — the search text is trimmed.
    Rules: _apply_item_catalog_filters R9."""
    a = mk(db, w1, "Zeta Rod")
    mk(db, w1, "Plain Nut")
    assert af_ids(db, w1, search="  zeta  ") == srt(a)


def test_item_af_24__inner_whitespace_kept(db, w1):
    """ITEM-AF-24 — two inner spaces do not match a single space.
    Rules: _apply_item_catalog_filters R9."""
    mk(db, w1, "Hex Bolt")
    assert af_ids(db, w1, search="hex  bolt") == []


def test_item_af_25__inner_single_space_matches(db, w1):
    """ITEM-AF-25 — one inner space matches.
    Rules: _apply_item_catalog_filters R9."""
    a = mk(db, w1, "Hex Bolt")
    assert af_ids(db, w1, search="hex bolt") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_item_af_26__underscore_literal_in_sku(db, w1):
    """ITEM-AF-26 — "AB_12" matches SKU "AB_12" but not "ABX12".
    Rules: _apply_item_catalog_filters R9 [BUG-013]."""
    a = mk(db, w1, "Clamp", sku="AB_12")
    b = mk(db, w1, "Clip", sku="ABX12")
    result = af_ids(db, w1, search="AB_12")
    assert result == srt(a)
    assert b.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_item_af_27__percent_literal(db, w1):
    """ITEM-AF-27 — "50%" matches only text containing "50%".
    Rules: _apply_item_catalog_filters R9 [BUG-013]."""
    a = mk(db, w1, "Cement 50% mix")
    b = mk(db, w1, "50 kg bag")
    c = mk(db, w1, "500 ml bottle")
    result = af_ids(db, w1, search="50%")
    assert result == srt(a)
    assert b.id not in result and c.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_item_af_28__underscore_alone(db, w1):
    """ITEM-AF-28 — "_" alone matches only items containing "_".
    Rules: _apply_item_catalog_filters R9 [BUG-013]."""
    a = mk(db, w1, "snake_case bolt")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="_") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_item_af_29__percent_alone(db, w1):
    """ITEM-AF-29 — "%" alone matches only items containing "%".
    Rules: _apply_item_catalog_filters R9 [BUG-013]."""
    a = mk(db, w1, "100% cotton rag")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="%") == srt(a)


def test_item_af_30__digit_search_matches_id_or_text(db, w1):
    """ITEM-AF-30 — an all-digit search matches the item with that id and text containing it.
    Rules: _apply_item_catalog_filters R11, R13."""
    a = mk(db, w1, "Hex Bolt")
    b = mk(db, w1, "Plain Bar")
    c = mk(db, w1, f"Pack {a.id}")
    result = af_ids(db, w1, search=str(a.id))
    assert result == srt(a, c)
    assert b.id not in result


def test_item_af_31__digit_search_trimmed_before_check(db, w1):
    """ITEM-AF-31 — " <id> " is trimmed and matches by id.
    Rules: _apply_item_catalog_filters R11."""
    a = mk(db, w1, "Hex Bolt")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search=f" {a.id} ") == srt(a)


def test_item_af_32__not_all_digits_no_id_match(db, w1):
    """ITEM-AF-32 — "<id>a" does not match by id.
    Rules: _apply_item_catalog_filters R11."""
    a = mk(db, w1, "Hex Bolt")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search=f"{a.id}a") == []


@pytest.mark.xfail(strict=True, reason="BUG-012: Catalog search with non-ASCII digits (e.g. `²`) crashes")
def test_item_af_33__superscript_digit_no_error(db, w1):
    """ITEM-AF-33 — "²" does not raise and matches by text only.
    Rules: _apply_item_catalog_filters R11 [BUG-012]; list_active_items_filtered R6."""
    a = mk(db, w1, "Sheet 2 m²")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="²") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-012: Catalog search with non-ASCII digits (e.g. `²`) crashes")
def test_item_af_34__mixed_superscript_digit_no_error(db, w1):
    """ITEM-AF-34 — "2²" does not raise and matches by text only.
    Rules: _apply_item_catalog_filters R11 [BUG-012]."""
    a = mk(db, w1, "Tile 2² grade")
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="2²") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-012: Catalog search with non-ASCII digits (e.g. `²`) crashes")
def test_item_af_35__arabic_indic_digits_no_id_match(db, w1):
    """ITEM-AF-35 — the id written in Arabic-Indic digits never matches by id.
    Rules: _apply_item_catalog_filters R11 [BUG-012]."""
    a = mk(db, w1, "Hex Bolt")
    mk(db, w1, "Plain Bar")
    arabic = "".join(chr(0x0660 + int(ch)) for ch in str(a.id))
    assert af_ids(db, w1, search=arabic) == []


def test_item_af_36__search_matches_active_tag_name(db, w1):
    """ITEM-AF-36 — search matches an item through an active tag's name.
    Rules: _apply_item_catalog_filters R12."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, t1)
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="GALV") == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-015: Catalog search matches names of deleted tags")
def test_item_af_37__search_ignores_deleted_tag_name(db, w1):
    """ITEM-AF-37 — search does not match through a deleted tag's name.
    Rules: _apply_item_catalog_filters R12 [BUG-015]."""
    tdel = mktag(db, w1, "Obsolete", active=False)
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, tdel)
    mk(db, w1, "Plain Bar")
    assert af_ids(db, w1, search="obsol") == []


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_item_af_38__underscore_literal_in_tag_name(db, w1):
    """ITEM-AF-38 — "a_b" matches tag "A_B grade" but not "AXB grade".
    Rules: _apply_item_catalog_filters R12, R9 [BUG-013]."""
    t1 = mktag(db, w1, "A_B grade")
    t2 = mktag(db, w1, "AXB grade")
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, t1)
    b = mk(db, w1, "Plain Nut")
    tag(db, b, t2)
    result = af_ids(db, w1, search="a_b")
    assert result == srt(a)
    assert b.id not in result


def test_item_af_39__tag_name_search_ignores_other_workspace_assignment(db, w1, w2):
    """ITEM-AF-39 — a tag-name match through an assignment in W2 does not count.
    Rules: _apply_item_catalog_filters R12."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, t1, ws_id=w2.id)
    assert af_ids(db, w1, search="galv") == []


def test_item_af_40__filters_and_combined(db, w1):
    """ITEM-AF-40 — search, unit and tag_ids combine with AND.
    Rules: _apply_item_catalog_filters R13."""
    t1 = mktag(db, w1, "Galvanized")
    a = mk(db, w1, "Zeta Rod", "kg")
    tag(db, a, t1)
    b = mk(db, w1, "Plain Bar", "kg")
    tag(db, b, t1)
    c = mk(db, w1, "Zeta Pin", "pcs")
    tag(db, c, t1)
    mk(db, w1, "Zeta Cap", "kg")
    assert af_ids(db, w1, search="zeta", unit="kg", tag_ids=[t1.id]) == srt(a)


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards (HR-8 backslash)")
def test_item_af_41__backslash_literal(db, w1):
    """ITEM-AF-41 — "a\\b" matches "a\\b" literally, not "ab".
    Rules: _apply_item_catalog_filters R9 [BUG-013] (HR-8)."""
    a = mk(db, w1, "Pipe a\\b fitting")
    b = mk(db, w1, "Pipe ab fitting")
    result = af_ids(db, w1, search="a\\b")
    assert result == srt(a)
    assert b.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards (HR-8 backslash)")
def test_item_af_42__backslash_alone(db, w1):
    """ITEM-AF-42 — "\\" alone matches only items containing a backslash.
    Rules: _apply_item_catalog_filters R9 [BUG-013] (HR-8)."""
    a = mk(db, w1, "Pipe a\\b fitting")
    b = mk(db, w1, "Plain Bar")
    c = mk(db, w1, "Discount rag %")
    result = af_ids(db, w1, search="\\")
    assert result == srt(a)
    assert b.id not in result and c.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards (HR-8 backslash)")
def test_item_af_43__trailing_backslash(db, w1):
    """ITEM-AF-43 — "abc\\" matches "abc\\" mid-name and does not raise.
    Rules: _apply_item_catalog_filters R9 [BUG-013] (HR-8)."""
    a = mk(db, w1, "Wrench abc\\ tool")
    b = mk(db, w1, "Plain abc%")
    c = mk(db, w1, "Plain Bar")
    result = af_ids(db, w1, search="abc\\")
    assert result == srt(a)
    assert b.id not in result and c.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards (HR-8 backslash)")
def test_item_af_44__backslash_literal_in_tag_name(db, w1):
    """ITEM-AF-44 — "a\\b" matches tag "a\\b grade" literally, not "ab grade".
    Rules: _apply_item_catalog_filters R12, R9 [BUG-013] (HR-8)."""
    t1 = mktag(db, w1, "a\\b grade")
    t2 = mktag(db, w1, "ab grade")
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, t1)
    b = mk(db, w1, "Plain Nut")
    tag(db, b, t2)
    result = af_ids(db, w1, search="a\\b")
    assert result == srt(a)
    assert b.id not in result


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_af_45__legacy_untrimmed_units_match(db, w1):
    """ITEM-AF-45 — unit="kg" matches stored "kg " and " KG".
    Rules: _apply_item_catalog_filters R4 [BUG-017] (Q14)."""
    a = mk(db, w1, "Rod", "kg ")
    b = mk(db, w1, "Bar", " KG")
    c = mk(db, w1, "Pin", "kgs")
    d = mk(db, w1, "Nut", "pcs")
    result = af_ids(db, w1, unit="kg")
    assert result == srt(a, b)
    assert c.id not in result and d.id not in result


def test_item_af_46__search_mid_sku(db, w1):
    """ITEM-AF-46 — search text in the middle of a sku matches.
    Rules: _apply_item_catalog_filters R9."""
    a = mk(db, w1, "Hex Bolt", "pcs", sku="XX-ZETA-YY")
    b = mk(db, w1, "Plain Bar", "pcs", sku="PN-AB")
    result = af_ids(db, w1, search="zeta")
    assert result == srt(a)
    assert b.id not in result


def test_item_af_47__search_mid_unit(db, w1):
    """ITEM-AF-47 — search text in the middle of a unit matches.
    Rules: _apply_item_catalog_filters R9."""
    a = mk(db, w1, "Rope", "bigzetaroll")
    b = mk(db, w1, "Plain Bar", "pcs")
    result = af_ids(db, w1, search="ZETA")
    assert result == srt(a)
    assert b.id not in result


def test_item_af_48__search_mid_tag_name(db, w1):
    """ITEM-AF-48 — search text in the middle of an active tag's name matches.
    Rules: _apply_item_catalog_filters R12."""
    t1 = mktag(db, w1, "Hot-dip galvanized")
    a = mk(db, w1, "Hex Bolt")
    tag(db, a, t1)
    b = mk(db, w1, "Plain Bar")
    result = af_ids(db, w1, search="GALV")
    assert result == srt(a)
    assert b.id not in result


# =========================================================================== #
# ItemDAO.list_active_items_filtered
# =========================================================================== #


def test_item_l_01__defaults_return_item_list(db, w1):
    """ITEM-L-01 — all defaults return a list of Item in name (= id) order.
    Rules: list_active_items_filtered R1, R3."""
    a = mk(db, w1, "Alpha Rod")
    b = mk(db, w1, "Bravo Bar")
    c = mk(db, w1, "Charlie Bolt")
    result = item_dao.list_active_items_filtered(db, workspace_id=w1.id)
    assert isinstance(result, list)
    assert all(isinstance(r, Item) for r in result)
    assert ids(result) == [a.id, b.id, c.id]
    assert_session_clean(db)


def test_item_l_02__multi_tag_item_once(db, w1):
    """ITEM-L-02 — an item carrying both requested tags appears once.
    Rules: list_active_items_filtered R2."""
    t1 = mktag(db, w1, "Galvanized")
    t2 = mktag(db, w1, "Painted")
    a = mk(db, w1, "Rod")
    tag(db, a, t1)
    tag(db, a, t2)
    b = mk(db, w1, "Bar")
    tag(db, b, t1)
    result = lst(db, w1, tag_ids=[t1.id, t2.id])
    assert len(result) == 2
    assert sorted(ids(result)) == srt(a, b)


def test_item_l_03__multi_tag_name_match_once(db, w1):
    """ITEM-L-03 — an item matching the search through two tags appears once.
    Rules: list_active_items_filtered R2."""
    t1 = mktag(db, w1, "Galvanized Steel")
    t2 = mktag(db, w1, "Galvanized Iron")
    a = mk(db, w1, "Galvanized Hex Bolt")
    tag(db, a, t1)
    tag(db, a, t2)
    mk(db, w1, "Plain Bar")
    result = lst(db, w1, search="galv")
    assert ids(result) == [a.id]
    assert len(result) == 1


@pytest.mark.xfail(strict=True, reason="BUG-033: Catalog item list ordered by `id` instead of name")
def test_item_l_04__ordered_by_name_case_insensitive(db, w1):
    """ITEM-L-04 — "Zulu", "Mike", "alpha" come back alpha, Mike, Zulu.
    Rules: list_active_items_filtered R3 [BUG-033]."""
    a = mk(db, w1, "Zulu")
    b = mk(db, w1, "Mike")
    c = mk(db, w1, "alpha")
    assert ids(lst(db, w1)) == [c.id, b.id, a.id]


def test_item_l_05__paging_after_filter(db, w1):
    """ITEM-L-05 — search then skip/limit windows partition the zeta items.
    Rules: list_active_items_filtered R3."""
    names = ["Zeta alpha", "Plain one", "Zeta bravo", "Zeta charlie", "Plain two", "Zeta delta", "Zeta echo"]
    for n in names:
        mk(db, w1, n)
    p1 = [r.name for r in lst(db, w1, search="zeta", skip=0, limit=2)]
    p2 = [r.name for r in lst(db, w1, search="zeta", skip=2, limit=2)]
    p3 = [r.name for r in lst(db, w1, search="zeta", skip=4, limit=2)]
    assert p1 == ["Zeta alpha", "Zeta bravo"]
    assert p2 == ["Zeta charlie", "Zeta delta"]
    assert p3 == ["Zeta echo"]
    together = p1 + p2 + p3
    assert sorted(together) == sorted(n for n in names if n.startswith("Zeta"))
    assert len(together) == len(set(together)) == 5
    assert not any(n.startswith("Plain") for n in together)


def test_item_l_06__default_limit_100(db, w1):
    """ITEM-L-06 — with 101 items the defaults return N(1)..N(100).
    Rules: list_active_items_filtered R4."""
    for k in range(1, 102):
        mk(db, w1, N(k))
    result = item_dao.list_active_items_filtered(db, workspace_id=w1.id)
    names = [r.name for r in result]
    assert len(result) == 100
    assert names == [N(k) for k in range(1, 101)]
    assert N(101) not in names


def test_item_l_07__exactly_100_items(db, w1):
    """ITEM-L-07 — with 100 items the defaults return all of them in order.
    Rules: list_active_items_filtered R4."""
    for k in range(1, 101):
        mk(db, w1, N(k))
    result = item_dao.list_active_items_filtered(db, workspace_id=w1.id)
    assert [r.name for r in result] == [N(k) for k in range(1, 101)]


def test_item_l_08__limit_zero_empty(db, w1):
    """ITEM-L-08 — limit=0 returns [].
    Rules: list_active_items_filtered R5."""
    mk(db, w1, "Rod")
    mk(db, w1, "Bar")
    mk(db, w1, "Pin")
    assert lst(db, w1, limit=0) == []


def test_item_l_09__limit_one(db, w1):
    """ITEM-L-09 — limit=1 returns the first item.
    Rules: list_active_items_filtered R5."""
    a = mk(db, w1, "Alpha Rod")
    mk(db, w1, "Bravo Bar")
    mk(db, w1, "Charlie Pin")
    assert ids(lst(db, w1, limit=1)) == [a.id]


@pytest.mark.parametrize(
    "kwargs, orig_cls, pgcode, message",
    [
        pytest.param(
            {"limit": -1},
            psycopg2.errors.InvalidRowCountInLimitClause,
            "2201W",
            "LIMIT must not be negative",
            id="ITEM-L-10",
        ),
        pytest.param(
            {"skip": -1},
            psycopg2.errors.InvalidRowCountInResultOffsetClause,
            "2201X",
            "OFFSET must not be negative",
            id="ITEM-L-11",
        ),
    ],
)
def test_item_l_10_11__negative_limit_or_skip_rejected(db, w1, kwargs, orig_cls, pgcode, message):
    """ITEM-L-10 / ITEM-L-11 — negative limit / skip raise DataError; nothing changes.
    Rules: list_active_items_filtered R5, Errors rows 1 and 2."""
    mk(db, w1, "Rod")
    mk(db, w1, "Bar")
    mk(db, w1, "Pin")
    before = snapshot(db, w1)
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            lst(db, w1, **kwargs)
    assert isinstance(exc.value.orig, orig_cls)
    assert exc.value.orig.pgcode == pgcode
    assert message in str(exc.value)
    after = snapshot(db, w1)
    assert len(after) == 3
    assert after == before


def test_item_l_12__unknown_workspace_empty(db, w1, w404):
    """ITEM-L-12 — an unknown workspace id returns [].
    Rules: list_active_items_filtered R1."""
    mk(db, w1, "Rod")
    assert item_dao.list_active_items_filtered(db, workspace_id=w404) == []


@pytest.mark.xfail(strict=True, reason="BUG-033: Catalog item list ordered by `id` instead of name")
def test_item_l_13__name_tie_broken_by_id(db, w1):
    """ITEM-L-13 — "bolt"/"Bolt" tie case-insensitively, lower id first, after "Axle".
    Rules: list_active_items_filtered R3 [BUG-033]."""
    a = mk(db, w1, "bolt")
    b = mk(db, w1, "Axle")
    c = mk(db, w1, "Bolt")
    assert ids(lst(db, w1)) == [b.id, a.id, c.id]


@pytest.mark.xfail(strict=True, reason="BUG-033: Catalog item list ordered by `id` instead of name")
def test_item_l_14__paging_in_name_order(db, w1):
    """ITEM-L-14 — pages follow name order even when it differs from id order.
    Rules: list_active_items_filtered R3 [BUG-033]."""
    names = ["Zeta echo", "Plain one", "Zeta delta", "Zeta charlie", "Plain two", "Zeta bravo", "Zeta alpha"]
    for n in names:
        mk(db, w1, n)
    p1 = [r.name for r in lst(db, w1, search="zeta", skip=0, limit=2)]
    p2 = [r.name for r in lst(db, w1, search="zeta", skip=2, limit=2)]
    p3 = [r.name for r in lst(db, w1, search="zeta", skip=4, limit=2)]
    assert p1 == ["Zeta alpha", "Zeta bravo"]
    assert p2 == ["Zeta charlie", "Zeta delta"]
    assert p3 == ["Zeta echo"]
    together = p1 + p2 + p3
    assert len(together) == len(set(together))


@pytest.mark.xfail(strict=True, reason="BUG-033: Catalog item list ordered by `id` instead of name")
def test_item_l_15__default_limit_uses_name_order(db, w1):
    """ITEM-L-15 — 101 items inserted N(101)..N(1): defaults return N(1)..N(100).
    Rules: list_active_items_filtered R4 [BUG-033]."""
    for k in range(101, 0, -1):
        mk(db, w1, N(k))
    result = item_dao.list_active_items_filtered(db, workspace_id=w1.id)
    names = [r.name for r in result]
    assert len(result) == 100
    assert names == [N(k) for k in range(1, 101)]
    assert N(101) not in names


# =========================================================================== #
# ItemDAO.count_active_items_filtered
# =========================================================================== #


def test_item_cnt_01__count_matches_list(db, w1, w2):
    """ITEM-CNT-01 — count equals the list length for the same filters.
    Rules: count_active_items_filtered R1."""
    mk(db, w1, "Zeta Rod")
    mk(db, w1, "Zeta Pin")
    mk(db, w1, "Plain Bar")
    mk(db, w1, "Zeta Cap", deleted=True)
    mk(db, w2, "Zeta Rod")
    result = cnt(db, w1, search="zeta")
    assert result == 2
    assert type(result) is int
    assert result == len(lst(db, w1, search="zeta", limit=100))
    assert_session_clean(db)


def test_item_cnt_02__count_not_capped(db, w1):
    """ITEM-CNT-02 — 150 items count as 150.
    Rules: count_active_items_filtered R1."""
    for k in range(1, 151):
        mk(db, w1, N(k))
    assert cnt(db, w1) == 150


def test_item_cnt_03__multi_tag_counted_once(db, w1):
    """ITEM-CNT-03 — an item with both requested tags counts once.
    Rules: count_active_items_filtered R2."""
    t1 = mktag(db, w1, "Galvanized")
    t2 = mktag(db, w1, "Painted")
    a = mk(db, w1, "Rod")
    tag(db, a, t1)
    tag(db, a, t2)
    b = mk(db, w1, "Bar")
    tag(db, b, t1)
    mk(db, w1, "Pin")
    assert cnt(db, w1, tag_ids=[t1.id, t2.id]) == 2


def test_item_cnt_04__multi_tag_name_match_counted_once(db, w1):
    """ITEM-CNT-04 — an item matching the search through two tags counts once.
    Rules: count_active_items_filtered R2."""
    t1 = mktag(db, w1, "Galvanized Steel")
    t2 = mktag(db, w1, "Galvanized Iron")
    a = mk(db, w1, "Galvanized Hex Bolt")
    tag(db, a, t1)
    tag(db, a, t2)
    mk(db, w1, "Plain Bar")
    assert cnt(db, w1, search="galv") == 1


def test_item_cnt_05__empty_workspace_zero(db, w1):
    """ITEM-CNT-05 — an empty workspace counts 0 as an int.
    Rules: count_active_items_filtered R3."""
    result = cnt(db, w1)
    assert result == 0
    assert isinstance(result, int) and result is not None


def test_item_cnt_06__unknown_workspace_zero(db, w1, w404):
    """ITEM-CNT-06 — an unknown workspace counts 0.
    Rules: count_active_items_filtered R3."""
    mk(db, w1, "Rod")
    result = item_dao.count_active_items_filtered(db, workspace_id=w404)
    assert result == 0
    assert isinstance(result, int)


def test_item_cnt_07__no_match_zero(db, w1):
    """ITEM-CNT-07 — a search with no match counts 0.
    Rules: count_active_items_filtered R3."""
    mk(db, w1, "Zeta Rod")
    mk(db, w1, "Plain Bar")
    result = cnt(db, w1, search="nomatch")
    assert result == 0
    assert isinstance(result, int)


@pytest.mark.xfail(strict=True, reason="BUG-012: Catalog search with non-ASCII digits (e.g. `²`) crashes")
def test_item_cnt_08__superscript_digit_no_error(db, w1):
    """ITEM-CNT-08 — count(search="²") does not raise and returns 1.
    Rules: count_active_items_filtered R4 [BUG-012]."""
    mk(db, w1, "Sheet 2 m²")
    mk(db, w1, "Plain Bar")
    assert cnt(db, w1, search="²") == 1


# =========================================================================== #
# ItemDAO.distinct_units_in_workspace
# =========================================================================== #


def _mk_units(db, ws, *unit_values, deleted=False):
    for i, u in enumerate(unit_values):
        mk(db, ws, f"Item {N(i + 1)}", u, deleted=deleted)


def test_item_u_01__distinct_sorted(db, w1):
    """ITEM-U-01 — each unit once, sorted.
    Rules: distinct_units_in_workspace R1, R5."""
    _mk_units(db, w1, "pcs", "kg", "ltr", "kg")
    assert units(db, w1.id) == ["kg", "ltr", "pcs"]
    assert_session_clean(db)


def test_item_u_02__deleted_and_other_workspace_excluded(db, w1, w2):
    """ITEM-U-02 — units of deleted items or other workspaces are not listed.
    Rules: distinct_units_in_workspace R2."""
    mk(db, w1, "Rod", "kg")
    mk(db, w1, "Crate", "box", deleted=True)
    mk(db, w2, "Barrel", "drum")
    assert units(db, w1.id) == ["kg"]


def test_item_u_03__empty_unit_not_listed(db, w1):
    """ITEM-U-03 — "" is never returned.
    Rules: distinct_units_in_workspace R3."""
    _mk_units(db, w1, "kg", "")
    assert units(db, w1.id) == ["kg"]


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_04__whitespace_unit_not_listed(db, w1):
    """ITEM-U-04 — a whitespace-only unit counts as "" and is not listed.
    Rules: distinct_units_in_workspace R3a [BUG-017]."""
    _mk_units(db, w1, "kg", " ")
    assert units(db, w1.id) == ["kg"]


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_05__case_variants_merged(db, w1):
    """ITEM-U-05 — kg, Kg, KG are one entry "kg".
    Rules: distinct_units_in_workspace R4 [BUG-017]."""
    _mk_units(db, w1, "kg", "Kg", "KG")
    assert units(db, w1.id) == ["kg"]


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_06__entry_lowercased(db, w1):
    """ITEM-U-06 — a lone "PCS" is listed as "pcs".
    Rules: distinct_units_in_workspace R4 [BUG-017]."""
    _mk_units(db, w1, "PCS")
    assert units(db, w1.id) == ["pcs"]


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_07__lowercased_and_sorted(db, w1):
    """ITEM-U-07 — PCS, kg, Ltr -> ["kg", "ltr", "pcs"].
    Rules: distinct_units_in_workspace R5, R4 [BUG-017]."""
    _mk_units(db, w1, "PCS", "kg", "Ltr")
    assert units(db, w1.id) == ["kg", "ltr", "pcs"]


def test_item_u_08__no_limit(db, w1):
    """ITEM-U-08 — 120 distinct units are all returned, sorted.
    Rules: distinct_units_in_workspace R6, R5."""
    _mk_units(db, w1, *[N(k) for k in range(1, 121)])
    assert units(db, w1.id) == sorted(N(k) for k in range(1, 121))


def test_item_u_09__empty_workspace(db, w1):
    """ITEM-U-09 — a workspace with no items returns [].
    Rules: distinct_units_in_workspace R6."""
    assert units(db, w1.id) == []


def test_item_u_10__unknown_workspace(db, w1, w404):
    """ITEM-U-10 — an unknown workspace returns [].
    Rules: distinct_units_in_workspace R6."""
    mk(db, w1, "Rod", "kg")
    assert units(db, w404) == []


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_11__only_blank_units(db, w1):
    """ITEM-U-11 — units "" and " " only -> [].
    Rules: distinct_units_in_workspace R3a [BUG-017]."""
    _mk_units(db, w1, "", " ")
    assert units(db, w1.id) == []


@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_item_u_12__legacy_untrimmed_merged(db, w1):
    """ITEM-U-12 — kg, Kg, KG, "kg " and pcs -> ["kg", "pcs"].
    Rules: distinct_units_in_workspace R4 [BUG-017] (Q14)."""
    _mk_units(db, w1, "kg", "Kg", "KG", "kg ", "pcs")
    assert units(db, w1.id) == ["kg", "pcs"]


# =========================================================================== #
# ItemDAO.find_similar_by_name_in_workspace
# =========================================================================== #


def _s01_setup(db, w1):
    a = mk(db, w1, "Steel Rod 22m", nn="steel rod 22m")
    b = mk(db, w1, "Copper Pipe", nn="copper pipe")
    return a, b


def test_item_s_01__exact_normalized_match(db, w1):
    """ITEM-S-01 — "Steel Rod 22 m" returns one tuple-like Row (A, 1.0).
    Rules: find_similar_by_name_in_workspace R3, R5."""
    a, b = _s01_setup(db, w1)
    result = similar(db, w1, "Steel Rod 22 m")
    assert type(result) is list
    assert len(result) == 1
    row = result[0]
    assert isinstance(row, Row)
    assert len(row) == 2
    assert isinstance(row[0], Item)
    assert row[0].id == a.id
    assert isinstance(row[1], float)
    assert row[1] == approx(1.0)
    item, score = row
    assert (item.id, score) == (a.id, approx(1.0))
    assert b.id not in [p[0] for p in pairs(result)]
    assert_session_clean(db)
    # Per the cases file: no assertion on isinstance(row, tuple) either way.


def test_item_s_02__spacing_case_punctuation_variant(db, w1):
    """ITEM-S-02 — "  STEEL-Rod   22 m " normalizes to an exact match.
    Rules: find_similar_by_name_in_workspace R5."""
    a, _b = _s01_setup(db, w1)
    assert pairs(similar(db, w1, "  STEEL-Rod   22 m ")) == [(a.id, approx(1.0))]


@pytest.mark.parametrize(
    "stored, proposed",
    [
        pytest.param("a b", "a b", id="ITEM-S-03"),
        pytest.param("22m", "22 m", id="ITEM-S-04"),
    ],
)
def test_item_s_03_04__normalized_length_three_proceeds(db, w1, stored, proposed):
    """ITEM-S-03 / ITEM-S-04 — a normalized name of length exactly 3 is looked up.
    Rules: find_similar_by_name_in_workspace R1."""
    a = mk(db, w1, stored, nn=stored)
    assert a.id in [p[0] for p in pairs(similar(db, w1, proposed))]


def test_item_s_05__short_name_returns_empty_list_no_query(db, engine, w1):
    """ITEM-S-05 — "ab" returns [] (a real list) with 0 SQL statements.
    Rules: find_similar_by_name_in_workspace R1, R10."""
    mk(db, w1, "ab", nn="ab")
    with StatementCounter(engine) as counter:
        result = similar(db, w1, "ab")
    assert result == []
    assert type(result) is list
    assert counter.count == 0


@pytest.mark.parametrize(
    "item_name, item_nn, proposed",
    [
        pytest.param("ab", "ab", "  AB  ", id="ITEM-S-06"),
        pytest.param("x", "", "", id="ITEM-S-07"),
        pytest.param("x", "", "!!!", id="ITEM-S-08"),
    ],
)
def test_item_s_06_08__short_name_no_query(db, engine, w1, item_name, item_nn, proposed):
    """ITEM-S-06..08 — a normalized name shorter than 3 returns [] with 0 SQL statements.
    Rules: find_similar_by_name_in_workspace R1."""
    mk(db, w1, item_name, nn=item_nn)
    with StatementCounter(engine) as counter:
        result = similar(db, w1, proposed)
    assert result == []
    assert counter.count == 0


def test_item_s_09__judged_by_name_normalized(db, w1):
    """ITEM-S-09 — matching uses name_normalized, not name.
    Rules: find_similar_by_name_in_workspace R2."""
    a = mk(db, w1, "Copper Pipe", nn="steel rod 22m")
    b = mk(db, w1, "Steel Rod 22m", nn="copper pipe")
    result = pairs(similar(db, w1, "Steel Rod 22m"))
    assert result == [(a.id, approx(1.0))]
    assert b.id not in [p[0] for p in result]


def test_item_s_10__exact_match_despite_low_score(db, w1):
    """ITEM-S-10 — an exact normalized match is returned even with score < 0.35.
    Rules: find_similar_by_name_in_workspace R3."""
    a = mk(db, w1, "___", nn="___")
    pre = sim(db, "___", "___")
    assert pre < 0.35
    result = similar(db, w1, "___")
    assert len(result) == 1
    assert result[0][0].id == a.id
    assert result[0][1] == approx(pre)


@pytest.mark.xfail(strict=True, reason="BUG-034: Similarity score of exactly 0.35 excluded")
def test_item_s_11__score_exactly_threshold_included(db, w1):
    """ITEM-S-11 — a score of exactly 0.35 (7/20) is included.
    Rules: find_similar_by_name_in_workspace R4a [BUG-034]."""
    a = mk(db, w1, "Abcdefghijklmnopqr", nn="abcdefghijklmnopqr")
    assert sim(db, "abcdefg", "abcdefghijklmnopqr") == pytest.approx(0.35, abs=1e-6)
    result = similar(db, w1, "abcdefg")
    assert len(result) == 1
    assert result[0][0].id == a.id
    assert result[0][1] == pytest.approx(0.3499999940395355, abs=1e-6)


def test_item_s_12__below_threshold_excluded(db, w1):
    """ITEM-S-12 — a score of 7/21 (< 0.35) is not returned.
    Rules: find_similar_by_name_in_workspace R4."""
    mk(db, w1, "Abcdefghijklmnopqrs", nn="abcdefghijklmnopqrs")
    pre = sim(db, "abcdefg", "abcdefghijklmnopqrs")
    assert pre == approx(0.3333)
    assert pre < 0.35
    assert similar(db, w1, "abcdefg") == []


def test_item_s_13__deleted_and_other_workspace_excluded(db, w1, w2):
    """ITEM-S-13 — deleted items and other workspaces are never returned.
    Rules: find_similar_by_name_in_workspace R6."""
    a = mk(db, w1, "Steel Rod 22m", nn="steel rod 22m")
    d = mk(db, w1, "Steel Rod 22m", nn="steel rod 22m", deleted=True)
    x = mk(db, w2, "Steel Rod 22m", nn="steel rod 22m")
    result = pairs(similar(db, w1, "Steel Rod 22m"))
    assert result == [(a.id, approx(1.0))]
    got = [p[0] for p in result]
    assert d.id not in got and x.id not in got


def test_item_s_14__default_limit_five(db, w1):
    """ITEM-S-14 — six exact matches, default limit returns five distinct ones.
    Rules: find_similar_by_name_in_workspace R7."""
    six = [mk(db, w1, f"Rod {w}", nn="steel rod 22m") for w in ("one", "two", "three", "four", "five", "six")]
    result = pairs(similar(db, w1, "Steel Rod 22m"))
    assert len(result) == 5
    assert all(score == approx(1.0) for _, score in result)
    got = [i for i, _ in result]
    assert len(set(got)) == 5
    assert set(got) <= {i.id for i in six}


def _three_exact(db, w1):
    return [mk(db, w1, f"Rod {w}", nn="steel rod 22m") for w in ("one", "two", "three")]


def test_item_s_15__limit_one(db, w1):
    """ITEM-S-15 — limit=1 returns one row with score 1.0.
    Rules: find_similar_by_name_in_workspace R7."""
    _three_exact(db, w1)
    result = pairs(similar(db, w1, "Steel Rod 22m", limit=1))
    assert len(result) == 1
    assert result[0][1] == approx(1.0)


def test_item_s_16__limit_zero(db, w1):
    """ITEM-S-16 — limit=0 returns [].
    Rules: find_similar_by_name_in_workspace R7."""
    _three_exact(db, w1)
    assert similar(db, w1, "Steel Rod 22m", limit=0) == []


def test_item_s_17__negative_limit_rejected(db, w1):
    """ITEM-S-17 — limit=-1 raises DataError (2201W); nothing changes.
    Rules: find_similar_by_name_in_workspace R7, Errors row 1."""
    _three_exact(db, w1)
    before = snapshot(db, w1)
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            similar(db, w1, "Steel Rod 22m", limit=-1)
    assert isinstance(exc.value.orig, psycopg2.errors.InvalidRowCountInLimitClause)
    assert exc.value.orig.pgcode == "2201W"
    assert "LIMIT must not be negative" in str(exc.value)
    after = snapshot(db, w1)
    assert len(after) == 3
    assert after == before


def _s18_setup(db, w1):
    a = mk(db, w1, "Steel Rod 22m", nn="steel rod 22m")
    b = mk(db, w1, "Steel Rod 22 m", nn="steel rod 22m")
    return a, b


def test_item_s_18__excluded_item_absent(db, w1):
    """ITEM-S-18 — exclude_item_id=A leaves A out despite exact match.
    Rules: find_similar_by_name_in_workspace R8."""
    a, b = _s18_setup(db, w1)
    result = pairs(similar(db, w1, "Steel Rod 22m", exclude_item_id=a.id))
    assert result == [(b.id, approx(1.0))]
    assert a.id not in [p[0] for p in result]


def test_item_s_19__exclude_unknown_id_no_effect(db, w1):
    """ITEM-S-19 — excluding a non-existent id has no effect.
    Rules: find_similar_by_name_in_workspace R8."""
    a, b = _s18_setup(db, w1)
    missing = (db.scalar(select(func.max(Item.id))) or 0) + 1000
    result = similar(db, w1, "Steel Rod 22m", exclude_item_id=missing)
    assert {r[0].id for r in result} == {a.id, b.id}


def test_item_s_20__exclude_non_candidate_no_effect(db, w1):
    """ITEM-S-20 — excluding an item that is not a candidate has no effect.
    Rules: find_similar_by_name_in_workspace R8."""
    a, b = _s18_setup(db, w1)
    c = mk(db, w1, "Copper Pipe", nn="copper pipe")
    result = similar(db, w1, "Steel Rod 22m", exclude_item_id=c.id)
    assert {r[0].id for r in result} == {a.id, b.id}


@pytest.mark.parametrize(
    "exclude",
    [pytest.param(None, id="ITEM-S-21"), pytest.param(0, id="ITEM-S-22")],
)
def test_item_s_21_22__exclude_none_or_zero(db, w1, exclude):
    """ITEM-S-21 / ITEM-S-22 — exclude_item_id None or 0 excludes nothing.
    Rules: find_similar_by_name_in_workspace R8."""
    a, b = _s18_setup(db, w1)
    result = similar(db, w1, "Steel Rod 22m", exclude_item_id=exclude)
    assert {r[0].id for r in result} == {a.id, b.id}


def _s23_setup(db, w1):
    p = mk(db, w1, "Pa", nn="abcdefghijklmnopq")
    q = mk(db, w1, "Qa", nn="abcdefghij")
    r = mk(db, w1, "Ra", nn="abcdefg")
    return p, q, r


def test_item_s_23__ordered_by_score_desc(db, w1):
    """ITEM-S-23 — rows come back by score descending.
    Rules: find_similar_by_name_in_workspace R9, R4."""
    p, q, r = _s23_setup(db, w1)
    assert pairs(similar(db, w1, "abcdefg")) == [
        (r.id, approx(1.0)),
        (q.id, approx(7 / 12)),
        (p.id, approx(7 / 19)),
    ]


def test_item_s_24__order_before_limit(db, w1):
    """ITEM-S-24 — limit=1 keeps the best score.
    Rules: find_similar_by_name_in_workspace R9, R7."""
    _p, _q, r = _s23_setup(db, w1)
    assert pairs(similar(db, w1, "abcdefg", limit=1)) == [(r.id, approx(1.0))]


_S25_NAMES = ["delta", "Bravo", "alpha", "Charlie", "echo", "Foxtrot", "bravo"]


@pytest.mark.xfail(
    strict=False,
    reason="BUG-018: Similar-name suggestions with tied scores in no fixed order "
    "(non-strict: today's tie order is the physical row order, which can match by accident)",
)
def test_item_s_25__ties_by_name_then_id_before_limit(db, w1):
    """ITEM-S-25 — 7 ties at 1.0, limit=5 -> alpha, Bravo, bravo, Charlie, delta.
    Rules: find_similar_by_name_in_workspace R9 [BUG-018]."""
    for n in _S25_NAMES:
        mk(db, w1, n, nn="steel rod 22m")
    result = similar(db, w1, "Steel Rod 22m", limit=5)
    names = [r[0].name for r in result]
    assert names == ["alpha", "Bravo", "bravo", "Charlie", "delta"]
    assert "echo" not in names and "Foxtrot" not in names
    assert all(r[1] == approx(1.0) for r in result)


@pytest.mark.xfail(
    strict=False,
    reason="BUG-018: Similar-name suggestions with tied scores in no fixed order "
    "(non-strict: today's tie order is the physical row order, which can match by accident)",
)
def test_item_s_26__ties_by_name_then_id(db, w1):
    """ITEM-S-26 — 7 ties at 1.0, limit=10 -> alpha, Bravo, bravo, Charlie, delta, echo, Foxtrot.
    Rules: find_similar_by_name_in_workspace R9 [BUG-018]."""
    for n in _S25_NAMES:
        mk(db, w1, n, nn="steel rod 22m")
    names = [r[0].name for r in similar(db, w1, "Steel Rod 22m", limit=10)]
    assert names == ["alpha", "Bravo", "bravo", "Charlie", "delta", "echo", "Foxtrot"]


def test_item_s_27__above_threshold_included(db, w1):
    """ITEM-S-27 — a score of 7/19 (> 0.35) is returned without an exact match.
    Rules: find_similar_by_name_in_workspace R4."""
    a = mk(db, w1, "Abcdefghijklmnopq", nn="abcdefghijklmnopq")
    pre = sim(db, "abcdefg", "abcdefghijklmnopq")
    assert pre == approx(0.3684)
    assert pre > 0.35
    assert pairs(similar(db, w1, "abcdefg")) == [(a.id, approx(0.3684))]


@pytest.mark.xfail(strict=True, reason="BUG-018: Similar-name suggestions with tied scores in no fixed order")
def test_item_s_28__order_by_has_name_and_id_tie_breakers(db, w1):
    """ITEM-S-28 — the similar-name query breaks score ties by name ignoring case, then id.
    Rules: find_similar_by_name_in_workspace R9 [BUG-018]."""
    a = mk(db, w1, "alpha", nn="steel rod 22m")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = similar(db, w1, "Steel Rod 22m")
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert [r[0].id for r in result] == [a.id]
    # Then 2
    selects = [" ".join(st.lower().split()) for st in statements if st.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    order = selects[0].split(" order by ", 1)[1] if " order by " in selects[0] else ""
    assert "lower(items.name)" in order
    assert "items.id" in order
