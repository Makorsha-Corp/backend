"""Unit tests for app/utils/audit_logger.py.

Implements tests/unit/utils/audit_logger.cases.md (revision 4), one test per
case. `log_financial_audit` cases use the real Postgres session (`db`
fixture); `create_change_dict` / `extract_relevant_fields` cases are pure (no
DB, no mocks). Only mock: the spec's external `app.utils.audit_logger.utcnow`,
patched around every `log_financial_audit` call (helper `call`).
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (prescribed by the cards: nested with, naive datetimes, Decimal("...") literals)
import copy
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm.collections import InstrumentedList

from app.models.financial_audit_log import FinancialAuditLog
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.utils.audit_logger import (
    create_change_dict,
    extract_relevant_fields,
    log_financial_audit,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Clock": NOW (naive, far from the DB clock)
NOW = datetime(2001, 2, 3, 4, 5, 6, 789000)

BUG_141 = "BUG-141: Money amounts stored in the audit JSON as floats"
BUG_142 = "BUG-142: Non-JSON value in audit changes fails the business operation"
BUG_143 = "BUG-143: Plain Enum fields silently dropped from audit snapshots"
BUG_144 = "BUG-144: Over-long user agent / IP fails the audit write and the operation"


# Convention "Test-only types"
class Status(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Color(str, Enum):
    RED = "red"


class Level(IntEnum):
    HIGH = 3


class Money(Enum):
    X = Decimal("9.90")


class Custom:
    def __init__(self):
        self.attr = 1

    def __str__(self):
        return "custom-obj"


class RelList(list):
    pass


class MyStr(str):
    pass


class MyInt(int):
    pass


class MyFloat(float):
    pass


U = UUID("12345678-1234-5678-1234-567812345678")


# Convention "W1, W2 = two workspaces; U1 = a profile in W1"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def u1(db):
    return make_profile(db)


# Convention "Minimal call (MIN)": cases list only what they add or change
def MIN(w1, u1, **overrides):
    kw = dict(
        workspace_id=w1.id,
        entity_type="account",
        entity_id=42,
        action_type="create",
        performed_by=u1.id,
    )
    kw.update(overrides)
    return kw


# Convention "Clock": every log_financial_audit call runs with
# app.utils.audit_logger.utcnow patched to NOW
def call(db, **kw):
    with patch("app.utils.audit_logger.utcnow", return_value=NOW):
        return log_financial_audit(db, **kw)


# Convention "Re-read": expire_all, then select rows by workspace ordered by id
def ws_rows(db, ws_id):
    db.expire_all()
    return db.execute(
        select(FinancialAuditLog)
        .where(FinancialAuditLog.workspace_id == ws_id)
        .order_by(FinancialAuditLog.id)
    ).scalars().all()


def ws_count(db, ws_id):
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(FinancialAuditLog)
        .where(FinancialAuditLog.workspace_id == ws_id)
    )


def only_row(db, ws_id):
    rows = ws_rows(db, ws_id)
    assert len(rows) == 1
    return rows[0]


# Raw SQL for "stored as SQL NULL" (JSON null vs SQL NULL, see cases Reviewer summary)
def is_null(db, row_id, column):
    return db.execute(
        text(f"SELECT {column} IS NULL FROM financial_audit_logs WHERE id = :id"),
        {"id": row_id},
    ).scalar_one()


# Convention "Unknown id": max(id) + 1000 (or 1000 if empty)
def unknown_id(db, model):
    return (db.scalar(select(func.max(model.id))) or 0) + 1000


# Standard object for AUD-X-01..04
def std_obj():
    return SimpleNamespace(name="Cash", code=101, rate=1.5, active=True, note=None)


# --------------------------------------------------------------------------- #
# log_financial_audit
# --------------------------------------------------------------------------- #

def test_aud_l_01__minimal_call_writes_one_row(db, w1, w2, u1):
    """AUD-L-01 — MIN writes exactly one row with the given values, NOW, and NULL optionals.
    Rules: log_financial_audit R1, R2, R3."""
    assert call(db, **MIN(w1, u1)) is None
    rows = ws_rows(db, w1.id)
    assert len(rows) == 1
    r = rows[0]
    assert r.id is not None
    assert r.workspace_id == w1.id
    assert r.entity_type == "account"
    assert r.entity_id == 42
    assert r.action_type == "create"
    assert r.performed_by == u1.id
    assert r.performed_at == NOW
    assert r.performed_at.tzinfo is None
    assert r.description is None
    assert r.related_entity_type is None
    assert r.related_entity_id is None
    assert r.ip_address is None
    assert r.user_agent is None
    assert is_null(db, r.id, "changes") is True
    assert ws_count(db, w2.id) == 0


def test_aud_l_02__optional_values_stored(db, w1, u1):
    """AUD-L-02 — all six optional values given are stored as given.
    Rules: log_financial_audit R3, R5."""
    ch = {"before": {"name": "Cash"}, "after": {"name": "Petty Cash"}}
    ret = call(
        db,
        **MIN(
            w1, u1,
            changes=ch,
            description="Renamed account",
            related_entity_type="invoice",
            related_entity_id=7,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 (X11; Linux x86_64)",
        ),
    )
    assert ret is None
    r = only_row(db, w1.id)
    assert r.changes == {"before": {"name": "Cash"}, "after": {"name": "Petty Cash"}}
    assert r.description == "Renamed account"
    assert r.related_entity_type == "invoice"
    assert r.related_entity_id == 7
    assert r.ip_address == "203.0.113.7"
    assert r.user_agent == "Mozilla/5.0 (X11; Linux x86_64)"


def test_aud_l_03__explicit_none_stored_as_sql_null(db, w1, u1):
    """AUD-L-03 — optional args passed explicitly as None are stored as SQL NULL.
    Rules: log_financial_audit R3."""
    ret = call(
        db,
        **MIN(
            w1, u1,
            changes=None, description=None, related_entity_type=None,
            related_entity_id=None, ip_address=None, user_agent=None,
        ),
    )
    assert ret is None
    r = only_row(db, w1.id)
    for col in ("changes", "description", "related_entity_type",
                "related_entity_id", "ip_address", "user_agent"):
        assert is_null(db, r.id, col) is True, col


def test_aud_l_04__json_native_changes_round_trip(db, w1, u1):
    """AUD-L-04 — JSON-native changes (incl. nested None) stored equal; caller dict unchanged.
    Rules: log_financial_audit R4, R7b."""
    c = {"after": {"email": None, "count": 3, "rate": 1.5, "active": True,
                   "tags": ["a", "b"], "meta": {"k": "v"}}}
    snapshot = copy.deepcopy(c)
    assert call(db, **MIN(w1, u1, changes=c)) is None
    r = only_row(db, w1.id)
    assert r.changes == snapshot
    assert "email" in r.changes["after"]
    assert r.changes["after"]["email"] is None
    assert c == snapshot


def test_aud_l_05__empty_changes_stored_as_empty_object(db, w1, u1):
    """AUD-L-05 — changes={} is stored as {} and not as NULL.
    Rules: log_financial_audit R4."""
    assert call(db, **MIN(w1, u1, changes={})) is None
    r = only_row(db, w1.id)
    assert is_null(db, r.id, "changes") is False
    assert r.changes == {}


def test_aud_l_06__fifty_char_type_fields_accepted(db, w1, u1):
    """AUD-L-06 — exactly 50 chars in entity_type/action_type/related_entity_type is stored in full.
    Rules: log_financial_audit R6."""
    ret = call(db, **MIN(w1, u1, entity_type="e" * 50, action_type="a" * 50,
                         related_entity_type="r" * 50, related_entity_id=1))
    assert ret is None
    r = only_row(db, w1.id)
    assert r.entity_type == "e" * 50 and len(r.entity_type) == 50
    assert r.action_type == "a" * 50 and len(r.action_type) == 50
    assert r.related_entity_type == "r" * 50 and len(r.related_entity_type) == 50


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"entity_type": "e" * 51}, id="AUD-L-07"),
        pytest.param({"action_type": "a" * 51}, id="AUD-L-08"),
        pytest.param({"related_entity_type": "r" * 51, "related_entity_id": 1}, id="AUD-L-09"),
    ],
)
def test_aud_l_07_08_09__type_field_over_50_rejected(db, w1, u1, overrides):
    """AUD-L-07 / AUD-L-08 / AUD-L-09 — a 51-char entity/action/related type raises DataError; no row.
    Rules: log_financial_audit R6; Errors row 3."""
    with pytest.raises(DataError):
        with db.begin_nested():
            call(db, **MIN(w1, u1, **overrides))
    assert ws_count(db, w1.id) == 0


def test_aud_l_10__ua_255_and_ip_45_stored_unchanged(db, w1, u1):
    """AUD-L-10 — user_agent of 255 chars and ip_address of 45 chars are stored unchanged.
    Rules: log_financial_audit R6a."""
    assert call(db, **MIN(w1, u1, user_agent="U" * 255, ip_address="1" * 45)) is None
    r = only_row(db, w1.id)
    assert r.user_agent == "U" * 255
    assert r.ip_address == "1" * 45


@pytest.mark.xfail(strict=True, reason=BUG_144)
def test_aud_l_11__user_agent_truncated_to_255(db, w1, u1):
    """AUD-L-11 — a 256-char user_agent is stored as its first 255 chars, no error.
    Rules: log_financial_audit R6a [BUG-144]."""
    with db.begin_nested():
        ret = call(db, **MIN(w1, u1, user_agent="A" * 255 + "Z"))
    assert ret is None
    r = only_row(db, w1.id)
    assert r.user_agent == "A" * 255


@pytest.mark.xfail(strict=True, reason=BUG_144)
def test_aud_l_12__ip_address_truncated_to_45(db, w1, u1):
    """AUD-L-12 — a 46-char ip_address is stored as its first 45 chars, no error.
    Rules: log_financial_audit R6a [BUG-144]."""
    with db.begin_nested():
        ret = call(db, **MIN(w1, u1, ip_address="1" * 45 + "9"))
    assert ret is None
    r = only_row(db, w1.id)
    assert r.ip_address == "1" * 45


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_13__decimal_in_changes_stored_as_string(db, w1, u1):
    """AUD-L-13 — nested Decimal values in changes are written as exact strings, no error.
    Rules: log_financial_audit R7, R7a (Decimal) [BUG-142]."""
    ch = {"invoice_amount": {"before": Decimal("1500.00"), "after": Decimal("2000.00")}}
    with db.begin_nested():
        ret = call(db, **MIN(w1, u1, changes=ch))
    assert ret is None
    r = only_row(db, w1.id)
    assert r.changes == {"invoice_amount": {"before": "1500.00", "after": "2000.00"}}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_14__decimal_formats_fixed_point_strings(db, w1, u1):
    """AUD-L-14 — Decimals (exponent, tiny, big, negative, non-finite) stored as fixed-point strings.
    Rules: log_financial_audit R7a (Decimal formats) [BUG-142]."""
    ch = {"a": Decimal("1E+2"), "b": Decimal("1E-7"), "c": Decimal("1234567890123456.78"),
          "d": Decimal("-5.50"), "e": Decimal("NaN"), "f": Decimal("Infinity"),
          "g": Decimal("-Infinity")}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"a": "100", "b": "0.0000001", "c": "1234567890123456.78",
                         "d": "-5.50", "e": "NaN", "f": "Infinity", "g": "-Infinity"}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_15__datetime_date_time_iso_strings(db, w1, u1):
    """AUD-L-15 — datetime (naive/aware), date and time in changes become ISO strings.
    Rules: log_financial_audit R7a (datetime/date/time) [BUG-142]."""
    ch = {"dt": datetime(2026, 1, 2, 3, 4, 5),
          "dta": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
          "d": date(2026, 1, 2), "t": time(9, 30)}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"dt": "2026-01-02T03:04:05", "dta": "2026-01-02T03:04:05+00:00",
                         "d": "2026-01-02", "t": "09:30:00"}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_16__uuid_and_enum_converted(db, w1, u1):
    """AUD-L-16 — UUID becomes its string; plain Enum and Decimal-valued Enum become their converted value.
    Rules: log_financial_audit R7a (UUID, Enum) [BUG-142]."""
    ch = {"u": U, "status": Status.ACTIVE, "m": Money.X}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"u": "12345678-1234-5678-1234-567812345678",
                         "status": "active", "m": "9.90"}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_17__non_finite_floats_as_strings(db, w1, u1):
    """AUD-L-17 — nan/inf/-inf floats become "NaN"/"Infinity"/"-Infinity"; finite float unchanged.
    Rules: log_financial_audit R7a (non-finite float) [BUG-142]."""
    ch = {"a": float("nan"), "b": float("inf"), "c": float("-inf"), "d": 1.25}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"a": "NaN", "b": "Infinity", "c": "-Infinity", "d": 1.25}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_18__containers_converted_recursively(db, w1, u1):
    """AUD-L-18 — sets/frozensets become sorted lists; nested Decimal/date/tuple converted at every depth.
    Rules: log_financial_audit R7, R7a (containers) [BUG-142]."""
    ch = {"s": {10, 9}, "fs": frozenset({"b", "a"}),
          "nested": [{"x": Decimal("1.10")}, (Decimal("2"), "y")],
          "deep": {"lvl": {"when": date(2026, 1, 2)}}}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"s": [10, 9], "fs": ["a", "b"],
                         "nested": [{"x": "1.10"}, ["2", "y"]],
                         "deep": {"lvl": {"when": "2026-01-02"}}}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_19__fallback_str(db, w1, u1):
    """AUD-L-19 — timedelta, bytes and a custom object fall back to str().
    Rules: log_financial_audit R7a (fallback) [BUG-142]."""
    ch = {"td": timedelta(days=1), "b": b"ab", "obj": Custom()}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=ch))
    r = only_row(db, w1.id)
    assert r.changes == {"td": "1 day, 0:00:00", "b": "b'ab'", "obj": "custom-obj"}


def test_aud_l_20__tuple_nonstr_key_str_int_enum_serialised(db, w1, u1):
    """AUD-L-20 — tuples, non-str keys and str/int enum members are stored JSON-converted.
    Rules: log_financial_audit R7a (tuple, non-str key, str/int enum)."""
    ch = {"t": (1, "a"), 5: "five", "nested": {2: [True, None]},
          "se": Color.RED, "ie": Level.HIGH}
    assert call(db, **MIN(w1, u1, changes=ch)) is None
    r = only_row(db, w1.id)
    assert r.changes == {"t": [1, "a"], "5": "five", "nested": {"2": [True, None]},
                         "se": "red", "ie": 3}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_l_21__caller_changes_not_mutated(db, w1, u1):
    """AUD-L-21 — converted copy is stored; the caller's dict keeps its Decimal and set objects.
    Rules: log_financial_audit R7b [BUG-142]."""
    amt = Decimal("2000.00")
    tags = {"x"}
    c = {"after": {"amount": amt, "tags": tags}}
    with db.begin_nested():
        call(db, **MIN(w1, u1, changes=c))
    r = only_row(db, w1.id)
    assert r.changes == {"after": {"amount": "2000.00", "tags": ["x"]}}
    assert c["after"]["amount"] is amt
    assert c["after"]["tags"] is tags
    assert isinstance(c["after"]["tags"], set)
    assert c == {"after": {"amount": Decimal("2000.00"), "tags": {"x"}}}


def test_aud_l_22__unknown_workspace_integrity_error(db, u1):
    """AUD-L-22 — unknown workspace_id fails the flush with IntegrityError; no row written.
    Rules: log_financial_audit R8; Errors row 2."""
    bad_ws = unknown_id(db, Workspace)
    kw = dict(workspace_id=bad_ws, entity_type="account", entity_id=42,
              action_type="create", performed_by=u1.id)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            call(db, **kw)
    db.expire_all()
    assert db.scalar(
        select(func.count()).select_from(FinancialAuditLog)
        .where(FinancialAuditLog.performed_by == u1.id)
    ) == 0


def test_aud_l_23__unknown_profile_integrity_error(db, w1):
    """AUD-L-23 — unknown performed_by fails the flush with IntegrityError; no row written.
    Rules: log_financial_audit R8; Errors row 2."""
    bad_p = unknown_id(db, Profile)
    kw = dict(workspace_id=w1.id, entity_type="account", entity_id=42,
              action_type="create", performed_by=bad_p)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            call(db, **kw)
    assert ws_count(db, w1.id) == 0


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"entity_id": "abc"}, id="AUD-L-24"),
        pytest.param({"related_entity_id": "abc"}, id="AUD-L-25"),
        pytest.param({"changes": ["not", "a", "dict"]}, id="AUD-L-26"),
        pytest.param({"entity_type": 123}, id="AUD-L-28"),
    ],
)
def test_aud_l_24_25_26_28__invalid_input_validation_error(db, w1, u1, overrides):
    """AUD-L-24 / AUD-L-25 / AUD-L-26 / AUD-L-28 — un-coercible id, non-dict changes or non-str
    text raises pydantic ValidationError before anything is added.
    Rules: log_financial_audit R9; Errors row 1."""
    with pytest.raises(ValidationError):
        call(db, **MIN(w1, u1, **overrides))
    assert len(db.new) == 0
    assert ws_count(db, w1.id) == 0


def test_aud_l_27__numeric_string_ids_coerced(db, w1, u1):
    """AUD-L-27 — numeric-string entity_id / related_entity_id are coerced to ints.
    Rules: log_financial_audit R9 (other side)."""
    assert call(db, **MIN(w1, u1, entity_id="5", related_entity_id="8")) is None
    r = only_row(db, w1.id)
    assert r.entity_id == 5 and type(r.entity_id) is int
    assert r.related_entity_id == 8 and type(r.related_entity_id) is int


def test_aud_l_29__no_commit_rollback_removes_row(db, w1, u1):
    """AUD-L-29 — the function does not commit; rolling back the savepoint removes the row.
    Rules: log_financial_audit R10."""
    sp = db.begin_nested()
    call(db, **MIN(w1, u1))
    rows = ws_rows(db, w1.id)
    assert len(rows) == 1
    row_id = rows[0].id
    sp.rollback()
    db.expire_all()
    assert db.scalar(
        select(func.count()).select_from(FinancialAuditLog).where(FinancialAuditLog.id == row_id)
    ) == 0
    assert ws_count(db, w1.id) == 0


def test_aud_l_30__two_identical_calls_two_rows(db, w1, u1):
    """AUD-L-30 — two identical calls append two distinct rows.
    Rules: log_financial_audit R1."""
    assert call(db, **MIN(w1, u1)) is None
    assert call(db, **MIN(w1, u1)) is None
    rows = ws_rows(db, w1.id)
    assert len(rows) == 2
    a, b = rows
    assert a.id != b.id
    assert (a.entity_type, a.entity_id, a.action_type, a.performed_by) == \
        (b.entity_type, b.entity_id, b.action_type, b.performed_by)
    assert a.performed_at == NOW
    assert b.performed_at == NOW


def test_aud_l_31__no_pairing_or_format_checks(db, w1, u1):
    """AUD-L-31 — related type without id, a non-IP ip_address and a 10000-char description are stored.
    Rules: log_financial_audit R3 (no pairing / no format check)."""
    ret = call(db, **MIN(w1, u1, related_entity_type="invoice",
                         ip_address="not-an-ip", description="D" * 10000))
    assert ret is None
    r = only_row(db, w1.id)
    assert r.related_entity_type == "invoice"
    assert r.related_entity_id is None
    assert r.ip_address == "not-an-ip"
    assert r.description == "D" * 10000


# --------------------------------------------------------------------------- #
# create_change_dict
# --------------------------------------------------------------------------- #

def test_aud_cd_01__before_and_after():
    """AUD-CD-01 — both given: result holds the same before/after objects and nothing else.
    Rules: create_change_dict R1, R2, R5."""
    b = {"name": "A"}
    a = {"name": "B"}
    result = create_change_dict(before=b, after=a)
    assert result == {"before": {"name": "A"}, "after": {"name": "B"}}
    assert result["before"] is b
    assert result["after"] is a
    assert set(result) == {"before", "after"}


def test_aud_cd_02__before_only():
    """AUD-CD-02 — only before given: no "after" key.
    Rules: create_change_dict R1, R5."""
    b = {"name": "A"}
    result = create_change_dict(before=b)
    assert result == {"before": {"name": "A"}}
    assert "after" not in result
    assert result["before"] is b


def test_aud_cd_03__after_only():
    """AUD-CD-03 — only after given: no "before" key.
    Rules: create_change_dict R2, R5."""
    a = {"name": "B"}
    result = create_change_dict(after=a)
    assert result == {"after": {"name": "B"}}
    assert "before" not in result
    assert result["after"] is a


def test_aud_cd_04__empty_before_counts_as_given():
    """AUD-CD-04 — before={} is kept.
    Rules: create_change_dict R3."""
    b = {}
    result = create_change_dict(before=b)
    assert result == {"before": {}}
    assert result["before"] is b


def test_aud_cd_05__empty_after_counts_as_given():
    """AUD-CD-05 — after={} is kept.
    Rules: create_change_dict R3."""
    a = {}
    result = create_change_dict(after=a)
    assert result == {"after": {}}
    assert result["after"] is a


def test_aud_cd_06__no_args_fresh_empty_dicts():
    """AUD-CD-06 — no arguments returns a new empty dict each call.
    Rules: create_change_dict R4."""
    r1 = create_change_dict()
    r2 = create_change_dict()
    assert r1 == {}
    assert r2 == {}
    assert r1 is not r2
    r1["x"] = 1
    assert r2 == {}


def test_aud_cd_07__explicit_nones_empty():
    """AUD-CD-07 — before=None, after=None returns {}.
    Rules: create_change_dict R4."""
    assert create_change_dict(before=None, after=None) == {}


def test_aud_cd_08__no_type_check():
    """AUD-CD-08 — a non-dict before is stored by reference without a type check.
    Rules: create_change_dict R1 (no type check)."""
    b = [1, 2]
    result = create_change_dict(before=b)
    assert result == {"before": [1, 2]}
    assert result["before"] is b


# --------------------------------------------------------------------------- #
# extract_relevant_fields
# --------------------------------------------------------------------------- #

def test_aud_x_01__natives_copied_in_order():
    """AUD-X-01 — native values copied unchanged, keys in field order, a new dict.
    Rules: extract_relevant_fields R7 (natives), Returns."""
    o = std_obj()
    result = extract_relevant_fields(o, ["name", "code", "rate", "active", "note"])
    assert result == {"name": "Cash", "code": 101, "rate": 1.5, "active": True, "note": None}
    assert list(result) == ["name", "code", "rate", "active", "note"]
    assert result is not o.__dict__


def test_aud_x_02__order_follows_fields():
    """AUD-X-02 — key order follows the fields list.
    Rules: extract_relevant_fields Returns (order)."""
    result = extract_relevant_fields(std_obj(), ["note", "active", "name"])
    assert list(result) == ["note", "active", "name"]
    assert list(result.values()) == [None, True, "Cash"]


def test_aud_x_03__missing_attribute_skipped():
    """AUD-X-03 — a field the object lacks is left out without error.
    Rules: extract_relevant_fields R1."""
    result = extract_relevant_fields(std_obj(), ["name", "missing", "code"])
    assert result == {"name": "Cash", "code": 101}
    assert "missing" not in result


def test_aud_x_04__empty_fields():
    """AUD-X-04 — empty fields list returns {}.
    Rules: extract_relevant_fields R2."""
    result = extract_relevant_fields(std_obj(), [])
    assert isinstance(result, dict)
    assert result == {}


def test_aud_x_05__duplicate_field_later_read_wins():
    """AUD-X-05 — a duplicated field name keeps one key holding the later read.
    Rules: extract_relevant_fields Inputs (duplicates)."""

    class Counter:
        def __init__(self):
            self.reads = 0

        @property
        def n(self):
            # every read returns a distinct value (1, 2, 3, ...), whatever the
            # number of reads per field
            self.reads += 1
            return self.reads

    obj = Counter()
    result = extract_relevant_fields(obj, ["n", "n"])
    assert obj.reads >= 2
    assert result == {"n": obj.reads}
    assert len(result) == 1


@pytest.mark.xfail(strict=True, reason=BUG_141)
def test_aud_x_06__decimal_exact_string():
    """AUD-X-06 — a Decimal is stored as its exact string "2000.00".
    Rules: extract_relevant_fields R3 [BUG-141]."""
    result = extract_relevant_fields(SimpleNamespace(amount=Decimal("2000.00")), ["amount"])
    assert result["amount"] == "2000.00"
    assert type(result["amount"]) is str


@pytest.mark.xfail(strict=True, reason=BUG_141)
def test_aud_x_07__decimal_fixed_point_formats():
    """AUD-X-07 — big/exponent/tiny/negative Decimals are stored as fixed-point strings.
    Rules: extract_relevant_fields R3 [BUG-141]."""
    o = SimpleNamespace(big=Decimal("1234567890123456.78"), e=Decimal("1E+2"),
                        tiny=Decimal("1E-7"), neg=Decimal("-5.50"))
    result = extract_relevant_fields(o, ["big", "e", "tiny", "neg"])
    assert result == {"big": "1234567890123456.78", "e": "100", "tiny": "0.0000001", "neg": "-5.50"}


@pytest.mark.xfail(strict=True, reason=BUG_141)
def test_aud_x_08__decimal_non_finite_strings():
    """AUD-X-08 — non-finite Decimals become "NaN"/"Infinity"/"-Infinity"; result is strict JSON.
    Rules: extract_relevant_fields R3 (non-finite) [BUG-141]."""
    o = SimpleNamespace(a=Decimal("NaN"), b=Decimal("Infinity"), c=Decimal("-Infinity"))
    result = extract_relevant_fields(o, ["a", "b", "c"])
    assert result == {"a": "NaN", "b": "Infinity", "c": "-Infinity"}
    json.dumps(result, allow_nan=False)


def test_aud_x_09__decimal_kept_numerically_equal():
    """AUD-X-09 — a Decimal field is kept and numerically equal (regression, both before/after fix).
    Rules: extract_relevant_fields R3 (regression)."""
    result = extract_relevant_fields(SimpleNamespace(amount=Decimal("2000.00")), ["amount"])
    assert "amount" in result
    assert Decimal(str(result["amount"])) == Decimal("2000")


def test_aud_x_10__naive_datetime_iso():
    """AUD-X-10 — a naive datetime becomes its ISO string.
    Rules: extract_relevant_fields R4."""
    result = extract_relevant_fields(SimpleNamespace(at=datetime(2026, 1, 2, 3, 4, 5)), ["at"])
    assert result == {"at": "2026-01-02T03:04:05"}


def test_aud_x_11__aware_datetime_keeps_offset():
    """AUD-X-11 — aware datetimes keep their offset in the ISO string.
    Rules: extract_relevant_fields R4 (aware)."""
    o = SimpleNamespace(
        u=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        d6=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=6))),
    )
    result = extract_relevant_fields(o, ["u", "d6"])
    assert result == {"u": "2026-01-02T03:04:05+00:00", "d6": "2026-01-02T03:04:05+06:00"}


def test_aud_x_12__date_iso():
    """AUD-X-12 — a date becomes "YYYY-MM-DD".
    Rules: extract_relevant_fields R5."""
    result = extract_relevant_fields(SimpleNamespace(due=date(2026, 1, 2)), ["due"])
    assert result == {"due": "2026-01-02"}


def test_aud_x_13__complex_objects_omitted():
    """AUD-X-13 — custom objects, InstrumentedList and list subclasses with __dict__ are omitted.
    Rules: extract_relevant_fields R6."""
    o = SimpleNamespace(name="Cash", related=Custom(), items=InstrumentedList([1, 2]), rel=RelList([1]))
    result = extract_relevant_fields(o, ["name", "related", "items", "rel"])
    assert result == {"name": "Cash"}


def test_aud_x_14__primitive_subclasses_kept():
    """AUD-X-14 — str/int/float subclasses (with __dict__) are kept.
    Rules: extract_relevant_fields R6 (primitive subclasses kept)."""
    o = SimpleNamespace(s=MyStr("abc"), i=MyInt(7), f=MyFloat(2.5))
    result = extract_relevant_fields(o, ["s", "i", "f"])
    assert result == {"s": "abc", "i": 7, "f": 2.5}


@pytest.mark.xfail(strict=True, reason=BUG_143)
def test_aud_x_15__plain_enum_stored_as_value():
    """AUD-X-15 — a plain Enum member is stored as its plain .value.
    Rules: extract_relevant_fields R6a [BUG-143]."""
    result = extract_relevant_fields(SimpleNamespace(name="Cash", status=Status.ACTIVE), ["name", "status"])
    assert result == {"name": "Cash", "status": "active"}
    assert type(result["status"]) is str


@pytest.mark.xfail(strict=True, reason=BUG_143)
def test_aud_x_16__str_int_enum_stored_as_plain_value():
    """AUD-X-16 — str/int enum members are stored as plain str/int, not the member.
    Rules: extract_relevant_fields R6a [BUG-143]."""
    result = extract_relevant_fields(SimpleNamespace(c=Color.RED, lvl=Level.HIGH), ["c", "lvl"])
    assert type(result["c"]) is str
    assert type(result["lvl"]) is int
    assert result == {"c": "red", "lvl": 3}


def test_aud_x_17__str_int_enum_equal_to_value():
    """AUD-X-17 — str/int enum members compare equal to their value (regression).
    Rules: extract_relevant_fields R6a (regression)."""
    result = extract_relevant_fields(SimpleNamespace(c=Color.RED, lvl=Level.HIGH), ["c", "lvl"])
    assert result["c"] == "red"
    assert result["lvl"] == 3


@pytest.mark.xfail(strict=True, reason=BUG_143)
def test_aud_x_18__decimal_valued_enum_converted():
    """AUD-X-18 — an Enum whose value is a Decimal is stored as the decimal's string.
    Rules: extract_relevant_fields R6a, R7a [BUG-143]."""
    result = extract_relevant_fields(SimpleNamespace(m=Money.X), ["m"])
    assert result == {"m": "9.90"}


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_x_19__uuid_time_timedelta_converted():
    """AUD-X-19 — UUID, time and timedelta become strings; result is strict JSON.
    Rules: extract_relevant_fields R7 (UUID/time/timedelta) [BUG-142]."""
    o = SimpleNamespace(u=U, t=time(9, 30), td=timedelta(days=1))
    result = extract_relevant_fields(o, ["u", "t", "td"])
    assert result == {"u": "12345678-1234-5678-1234-567812345678", "t": "09:30:00",
                      "td": "1 day, 0:00:00"}
    json.dumps(result, allow_nan=False)


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_x_20__containers_converted_recursively():
    """AUD-X-20 — list/tuple/set/dict contents converted recursively; result is strict JSON.
    Rules: extract_relevant_fields R7 (containers) [BUG-142]."""
    o = SimpleNamespace(l=[Decimal("1.10"), date(2026, 1, 2)], tp=(1, Decimal("2")),
                        st={10, 9}, d={"k": Decimal("3.30"), 4: "four"})
    result = extract_relevant_fields(o, ["l", "tp", "st", "d"])
    assert result == {"l": ["1.10", "2026-01-02"], "tp": [1, "2"], "st": [10, 9],
                      "d": {"k": "3.30", "4": "four"}}
    json.dumps(result, allow_nan=False)


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_x_21__nested_custom_object_str():
    """AUD-X-21 — a custom object nested in a plain list becomes str(obj); result is strict JSON.
    Rules: extract_relevant_fields R7 (nested custom object) [BUG-142]."""
    result = extract_relevant_fields(SimpleNamespace(items=[Custom()]), ["items"])
    assert result == {"items": ["custom-obj"]}
    json.dumps(result, allow_nan=False)


def test_aud_x_22__json_native_containers_unchanged():
    """AUD-X-22 — JSON-native lists/dicts are kept equal; result is strict JSON.
    Rules: extract_relevant_fields R7 (JSON-native containers)."""
    o = SimpleNamespace(l=["a", 1, None], d={"k": "v", "n": [True]})
    result = extract_relevant_fields(o, ["l", "d"])
    assert result == {"l": ["a", 1, None], "d": {"k": "v", "n": [True]}}
    json.dumps(result, allow_nan=False)


@pytest.mark.xfail(strict=True, reason=BUG_142)
def test_aud_x_23__non_finite_float_strings():
    """AUD-X-23 — nan/inf/-inf floats become strings; finite float unchanged; strict JSON.
    Rules: extract_relevant_fields R7a (non-finite float) [BUG-142]."""
    o = SimpleNamespace(a=float("nan"), b=float("inf"), c=float("-inf"), d=1.25)
    result = extract_relevant_fields(o, ["a", "b", "c", "d"])
    assert result == {"a": "NaN", "b": "Infinity", "c": "-Infinity", "d": 1.25}
    json.dumps(result, allow_nan=False)


def test_aud_x_24__object_not_modified():
    """AUD-X-24 — the source object and its values are never modified.
    Rules: extract_relevant_fields R8."""
    amt = Decimal("2000.00")
    when = datetime(2026, 1, 2)
    tags = [Decimal("1.1")]
    o = SimpleNamespace(amount=amt, when=when, tags=tags)
    before = dict(vars(o))
    extract_relevant_fields(o, ["amount", "when", "tags"])
    assert o.amount is amt
    assert o.when is when
    assert o.tags is tags
    assert tags == [Decimal("1.1")]
    assert type(tags[0]) is Decimal
    assert vars(o) == before


def test_aud_x_25__non_attribute_error_propagates():
    """AUD-X-25 — an error other than AttributeError from attribute access propagates.
    Rules: extract_relevant_fields Errors (non-AttributeError)."""

    class Boom:
        @property
        def x(self):
            raise ValueError("boom")

    with pytest.raises(ValueError) as exc:
        extract_relevant_fields(Boom(), ["x"])
    assert str(exc.value) == "boom"


def test_aud_x_26__attribute_error_from_property_skipped():
    """AUD-X-26 — a property raising AttributeError is treated as missing.
    Rules: extract_relevant_fields R1 (AttributeError from property)."""

    class Half:
        name = "Cash"

        @property
        def y(self):
            raise AttributeError("y")

    result = extract_relevant_fields(Half(), ["name", "y"])
    assert result == {"name": "Cash"}
