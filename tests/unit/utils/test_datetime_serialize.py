"""Unit tests for app/utils/datetime_serialize.py.

Implements tests/unit/utils/datetime_serialize.cases.md (revision 2), one test
per case. `ensure_utc_z_in_json` is pure: no database, no app, no mocks.
`serialize_utc_datetime` is dead code (spec "Not specified") and has no cases.
"""
# ruff: noqa: DTZ001  (prescribed by the cards: naive datetimes)
import copy
from datetime import datetime

import pytest

from app.schemas.base import AppResponseModel
from app.utils.datetime_serialize import ensure_utc_z_in_json

# --------------------------------------------------------------------------- #
# Conventions -> helpers
# --------------------------------------------------------------------------- #

# Convention "f"
f = ensure_utc_z_in_json

# Convention "DT"
DT = "2026-01-01T10:00:00"

BUG_160 = (
    "BUG-160: Free-text strings shaped like a naive date-time get a `Z` "
    "appended in API responses"
)
BUG_161 = "BUG-161: Date-time followed by a trailing newline gets `Z` after the newline"
BUG_162 = "BUG-162: Non-ASCII digits treated as date-time digits"


def _make_m(**fields):
    """Convention "M": a throw-away AppResponseModel subclass.

    `fields` maps name -> (annotation, default).
    """
    annotations = {name: ann for name, (ann, _) in fields.items()}
    namespace = {name: default for name, (_, default) in fields.items()}
    namespace["__annotations__"] = annotations
    return type("M", (AppResponseModel,), namespace)


# --------------------------------------------------------------------------- #
# Strings
# --------------------------------------------------------------------------- #


def test_dts_e_01__naive_datetime_gains_z():
    """DTS-E-01 — a naive ISO date-time string gains a trailing Z.
    Rules: ensure_utc_z_in_json R4."""
    r = f(DT)
    assert r == "2026-01-01T10:00:00Z"
    assert isinstance(r, str)


@pytest.mark.parametrize(
    "s, expected",
    [
        pytest.param("2026-01-01T10:00:00.120000", "2026-01-01T10:00:00.120000Z", id="six-digits"),
        pytest.param("2026-01-01T10:00:00.5", "2026-01-01T10:00:00.5Z", id="one-digit"),
        pytest.param("2026-01-01T10:00:00.123456789", "2026-01-01T10:00:00.123456789Z", id="nine-digits"),
    ],
)
def test_dts_e_02__fraction_kept_verbatim(s, expected):
    """DTS-E-02 — fractional seconds are kept character for character, Z appended.
    Rules: ensure_utc_z_in_json R4."""
    r = f(s)
    assert r == s + "Z"
    assert r == expected


@pytest.mark.parametrize(
    "s",
    [
        pytest.param("2024-02-29T23:59:59", id="leap-day"),
        pytest.param("2026-02-28T12:00:00", id="feb-28"),
        pytest.param("2026-04-30T10:00:00", id="apr-30"),
        pytest.param("2026-12-31T23:59:59", id="dec-31"),
        pytest.param("2026-01-01T00:00:00", id="midnight"),
        pytest.param("2026-12-31T23:59:59.999999", id="last-microsecond"),
    ],
)
def test_dts_e_03__real_calendar_edges_gain_z(s):
    """DTS-E-03 — real calendar edge values gain Z.
    Rules: ensure_utc_z_in_json R4 (valid side of R4a)."""
    assert f(s) == s + "Z"


@pytest.mark.xfail(strict=True, reason=BUG_160)
@pytest.mark.parametrize(
    "s",
    [
        pytest.param("2026-13-01T10:00:00", id="month-13"),
        pytest.param("2026-00-01T10:00:00", id="month-0"),
        pytest.param("2026-01-32T10:00:00", id="day-32"),
        pytest.param("2026-01-00T10:00:00", id="day-0"),
        pytest.param("2026-02-30T10:00:00", id="feb-30"),
        pytest.param("2025-02-29T10:00:00", id="feb-29-non-leap"),
        pytest.param("2026-04-31T10:00:00", id="apr-31"),
        pytest.param("2026-01-01T24:00:00", id="hour-24"),
        pytest.param("2026-01-01T10:60:00", id="minute-60"),
        pytest.param("2026-01-01T10:00:60", id="second-60"),
        pytest.param("9999-99-99T99:99:99", id="all-nines"),
        pytest.param("2026-02-30T10:00:00.5", id="feb-30-fraction"),
    ],
)
def test_dts_e_04__invalid_calendar_value_unchanged(s):
    """DTS-E-04 — an impossible calendar value of the matching shape stays unchanged.
    Rules: ensure_utc_z_in_json R4a [BUG-160]."""
    assert f(s) == s


@pytest.mark.parametrize(
    "s",
    [
        pytest.param("2026-13-45T25:61:61", id="all-out-of-range"),
        pytest.param("9999-99-99T99:99:99", id="all-nines"),
    ],
)
def test_dts_e_05__invalid_values_never_raise(s):
    """DTS-E-05 — invalid values never raise; result is a str starting with s.
    Rules: ensure_utc_z_in_json R4a; Errors row "none"."""
    r = f(s)
    assert isinstance(r, str)
    assert r.startswith(s)


@pytest.mark.parametrize(
    "s",
    [
        pytest.param("2026-01-01T10:00:00Z", id="already-z"),
        pytest.param("2026-01-01T10:00:00.120000Z", id="fraction-z"),
        pytest.param("2026-01-01T10:00:00+06:00", id="plus-offset"),
        pytest.param("2026-01-01T10:00:00-05:00", id="minus-offset"),
        pytest.param("2026-01-01T10:00:00.5+06:00", id="fraction-offset"),
        pytest.param("2026-01-01", id="date-only"),
        pytest.param("2026-01-01 10:00:00", id="space-separator"),
        pytest.param("2026-01-01t10:00:00", id="lowercase-t"),
        pytest.param("2026-01-01T10:00", id="no-seconds"),
        pytest.param("2026-01-01T10:00:00.", id="empty-fraction"),
        pytest.param(" 2026-01-01T10:00:00", id="leading-space"),
        pytest.param("2026-01-01T10:00:00 ", id="trailing-space"),
        pytest.param("at 2026-01-01T10:00:00", id="prefix-text"),
        pytest.param("2026-01-01T10:00:00 UTC", id="suffix-text"),
        pytest.param("\n2026-01-01T10:00:00", id="leading-newline"),
        pytest.param("20260-01-01T10:00:00", id="five-digit-year"),
        pytest.param("226-01-01T10:00:00", id="three-digit-year"),
        pytest.param("2026-1-01T10:00:00", id="one-digit-month"),
        pytest.param("", id="empty"),
        pytest.param("hello", id="hello"),
    ],
)
def test_dts_e_06__non_matching_strings_unchanged(s):
    """DTS-E-06 — strings that are not exactly a naive date-time are unchanged.
    Rules: ensure_utc_z_in_json R5."""
    assert f(s) == s


@pytest.mark.xfail(strict=True, reason=BUG_161)
def test_dts_e_07__single_trailing_newline_unchanged():
    """DTS-E-07 — a date-time followed by one trailing newline is unchanged.
    Rules: ensure_utc_z_in_json R6 [BUG-161]."""
    assert f("2026-01-01T10:00:00\n") == "2026-01-01T10:00:00\n"


@pytest.mark.parametrize(
    "s",
    [
        pytest.param("2026-01-01T10:00:00\n\n", id="two-newlines"),
        pytest.param("2026-01-01T10:00:00\r\n", id="crlf"),
        pytest.param("2026-01-01T10:00:00\t", id="tab"),
        pytest.param("2026-01-01T10:00:00x", id="letter"),
    ],
)
def test_dts_e_08__other_trailing_characters_unchanged(s):
    """DTS-E-08 — other trailing characters leave the string unchanged.
    Rules: ensure_utc_z_in_json R6."""
    assert f(s) == s


@pytest.mark.xfail(strict=True, reason=BUG_162)
@pytest.mark.parametrize(
    "s",
    [
        pytest.param("٢٠٢٦-01-01T10:00:00", id="arabic-indic-year"),
        pytest.param("২০২৬-০১-০১T১০:০০:০০", id="all-bengali"),
        pytest.param("2026-01-01T10:00:00.১২", id="bengali-fraction"),
        pytest.param("２０２６-01-01T10:00:00", id="fullwidth-year"),
    ],
)
def test_dts_e_09__non_ascii_digits_unchanged(s):
    """DTS-E-09 — non-ASCII decimal digits do not count as date-time digits.
    Rules: ensure_utc_z_in_json R7 [BUG-162]."""
    assert f(s) == s


# --------------------------------------------------------------------------- #
# Containers
# --------------------------------------------------------------------------- #


def test_dts_e_10__dict_values_walked_new_dict_order_kept():
    """DTS-E-10 — dict values are walked into a new dict; order kept; input not mutated.
    Rules: ensure_utc_z_in_json R1; Side effects."""
    d = {"b": DT, "a": 1, "c": "x"}
    before = copy.deepcopy(d)
    r = f(d)
    assert r == {"b": "2026-01-01T10:00:00Z", "a": 1, "c": "x"}
    assert list(r.keys()) == ["b", "a", "c"]
    assert r is not d
    assert d == before
    assert d == {"b": DT, "a": 1, "c": "x"}


def test_dts_e_11__datetime_shaped_keys_untouched():
    """DTS-E-11 — dict keys are never rewritten, even when date-time shaped.
    Rules: ensure_utc_z_in_json R1."""
    d = {DT: DT, "k": "v"}
    r = f(d)
    assert r == {"2026-01-01T10:00:00": "2026-01-01T10:00:00Z", "k": "v"}
    assert "2026-01-01T10:00:00Z" not in r
    assert list(r.keys()) == [DT, "k"]


def test_dts_e_12__list_items_walked_new_list():
    """DTS-E-12 — list items are walked into a new list; input not mutated.
    Rules: ensure_utc_z_in_json R2; Side effects."""
    lst = [DT, 5, "x", None, "2026-01-01T10:00:00.5"]
    before = copy.deepcopy(lst)
    r = f(lst)
    assert r == ["2026-01-01T10:00:00Z", 5, "x", None, "2026-01-01T10:00:00.5Z"]
    assert type(r) is list
    assert len(r) == 5
    assert r is not lst
    assert lst == before


def test_dts_e_13__nested_structure_walked_recursively():
    """DTS-E-13 — nested dicts/lists are walked recursively into new containers.
    Rules: ensure_utc_z_in_json R1, R2; Side effects."""
    n = {
        "items": [{"at": DT, "tags": ["2026-01-01T10:00:00.5", {"deep": [[DT]]}]}],
        "meta": {"created": DT, "count": 2},
    }
    before = copy.deepcopy(n)
    r = f(n)
    assert r == {
        "items": [
            {
                "at": "2026-01-01T10:00:00Z",
                "tags": ["2026-01-01T10:00:00.5Z", {"deep": [["2026-01-01T10:00:00Z"]]}],
            }
        ],
        "meta": {"created": "2026-01-01T10:00:00Z", "count": 2},
    }
    assert r["items"] is not n["items"]
    assert r["meta"] is not n["meta"]
    assert n == before


def test_dts_e_14__empty_containers():
    """DTS-E-14 — empty dict and list come back as empty dict and list.
    Rules: ensure_utc_z_in_json R2, R1."""
    rd = f({})
    rl = f([])
    assert rd == {}
    assert type(rd) is dict
    assert rl == []
    assert type(rl) is list


def test_dts_e_15__deep_nesting_200_levels():
    """DTS-E-15 — 200 levels of alternating list/dict nesting are walked fully.
    Rules: ensure_utc_z_in_json R2 (depth 200: best-practice default, delegated by reviewer)."""
    depth = 200
    value = DT
    for i in range(depth):
        value = [value] if i % 2 == 0 else {"k": value}

    r = f(value)  # no exception

    for i in reversed(range(depth)):
        r = r[0] if i % 2 == 0 else r["k"]
    assert r == "2026-01-01T10:00:00Z"


def test_dts_e_16__tuples_and_sets_returned_as_is():
    """DTS-E-16 — tuples and sets are returned as is (same object, not walked).
    Rules: ensure_utc_z_in_json R3."""
    t = (DT,)
    s = {DT}
    lst = [DT, t]
    rt = f(t)
    assert rt is t
    assert rt == ("2026-01-01T10:00:00",)
    rs = f(s)
    assert rs is s
    assert rs == {"2026-01-01T10:00:00"}
    rl = f(lst)
    assert rl == ["2026-01-01T10:00:00Z", ("2026-01-01T10:00:00",)]
    assert rl[1] is t


@pytest.mark.parametrize(
    "v",
    [
        pytest.param(42, id="int"),
        pytest.param(0, id="zero"),
        pytest.param(3.5, id="float"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(None, id="none"),
        pytest.param(datetime(2026, 1, 1, 10, 0), id="datetime"),
    ],
)
def test_dts_e_17__scalars_returned_as_is(v):
    """DTS-E-17 — non-string scalars (incl. datetime objects) are returned as is.
    Rules: ensure_utc_z_in_json R8."""
    r = f(v)
    assert r is v
    if isinstance(v, datetime):
        assert isinstance(r, datetime)
        assert not isinstance(r, str)
        assert r == datetime(2026, 1, 1, 10, 0)


def test_dts_e_18__falsy_scalars_and_datetime_in_dict_kept():
    """DTS-E-18 — falsy scalars and datetime objects inside a dict are kept as is.
    Rules: ensure_utc_z_in_json R8, R1."""
    d = {"n": 0, "f": 0.0, "b": False, "x": None, "d": datetime(2026, 1, 1, 10, 0)}
    r = f(d)
    assert r == d
    assert r["d"] is d["d"]
    assert isinstance(r["d"], datetime)
    assert r["b"] is False
    assert r["x"] is None


# --------------------------------------------------------------------------- #
# Through AppResponseModel (schema-level target)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(strict=True, reason=BUG_160)
def test_dts_e_19__schema_str_field_not_rewritten():
    """DTS-E-19 — through AppResponseModel a str field keeps its value; datetime gains Z.
    Rules: ensure_utc_z_in_json R9 [BUG-160]."""
    M = _make_m(note=(str, "2026-01-01T10:00:00"), at=(datetime, datetime(2026, 1, 1, 10, 0)))
    result = M().model_dump(mode="json")
    assert result["note"] == "2026-01-01T10:00:00"
    assert result["at"] == "2026-01-01T10:00:00Z"


def test_dts_e_20__schema_datetime_field_gains_z():
    """DTS-E-20 — through AppResponseModel a naive datetime field serializes with Z.
    Rules: ensure_utc_z_in_json R9."""
    M = _make_m(note=(str, "hello"), at=(datetime, datetime(2026, 1, 1, 10, 0)))
    result = M().model_dump(mode="json")
    assert result == {"note": "hello", "at": "2026-01-01T10:00:00Z"}


# --------------------------------------------------------------------------- #
# Idempotence
# --------------------------------------------------------------------------- #


def test_dts_e_21__idempotent():
    """DTS-E-21 — applying the walk twice gives the same result as once.
    Rules: ensure_utc_z_in_json R10."""
    v = {
        "a": DT,
        "b": [
            DT + ".5",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00+06:00",
            "9999-99-99T99:99:99",
            "2026-01-01T10:00:00\n",
            "٢٠٢٦-01-01T10:00:00",
            "",
            7,
            None,
        ],
        "c": (DT,),
    }
    once = f(v)
    twice = f(once)
    assert twice == once
    assert once["a"] == "2026-01-01T10:00:00Z"
