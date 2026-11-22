"""Unit tests for app/core/waitlist_admin.py.

Implements tests/unit/core/waitlist_admin.cases.md (revision 2), one test per
case. `get_waitlist_admin` is a plain synchronous function; it is called
directly with `current_user=` passed explicitly (bypasses the Depends default).
Externals mocked: none. The only patch is the `settings.WAITLIST_ADMIN_EMAILS`
value, set explicitly in every test (cases Conventions "Allowlist").
"""
import types

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.waitlist_admin import get_waitlist_admin
from app.models.profile import Profile
from tests.unit.factories import make_profile

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Refusal": the intended detail everywhere (D-NA)
D_NA = "Not authorized to view waitlist signups"

BUG_540 = "BUG-540: HIGH — waitlist admin access granted by an unverified email"
BUG_541 = "BUG-541: Refusal message reveals server configuration"


# Convention "Allowlist": every test sets settings.WAITLIST_ADMIN_EMAILS explicitly
@pytest.fixture
def allowlist(monkeypatch):
    def _set(values):
        monkeypatch.setattr(settings, "WAITLIST_ADMIN_EMAILS", list(values), raising=False)

    return _set


# Convention "Saved profile P": a profiles row with the given email / flag
def saved_profile(db, email, is_platform_admin):
    return make_profile(db, email=email, is_platform_admin=is_platform_admin)


# Convention "Saved profile P ... row unchanged": fresh re-read + no pending changes
def assert_row_unchanged(db, p_id, email, is_platform_admin):
    db.expire_all()
    row = db.execute(
        select(Profile.email, Profile.is_platform_admin).where(Profile.id == p_id)
    ).one()
    assert row.email == email
    assert row.is_platform_admin == is_platform_admin
    assert not db.new
    assert not db.dirty


# Convention "Unsaved profile": in-memory Profile, never added to the session
def unsaved_profile(email, is_platform_admin):
    return Profile(email=email, is_platform_admin=is_platform_admin)


# Convention "Unsaved profile ... object unchanged"
def assert_obj_unchanged(obj, email, is_platform_admin):
    assert obj.email == email
    assert obj.is_platform_admin == is_platform_admin


# Convention "Bare object": no is_platform_admin attribute
def bare_object(email="member@makorsha.com"):
    return types.SimpleNamespace(email=email)


def assert_bare_unchanged(obj, email="member@makorsha.com"):
    assert obj.email == email
    assert hasattr(obj, "is_platform_admin") is False


# --------------------------------------------------------------------------- #
# get_waitlist_admin
# --------------------------------------------------------------------------- #


def test_wla_g_01__admin_admitted_with_empty_allowlist(db, allowlist):
    """WLA-G-01 — platform admin is returned (identity) with an empty allowlist.
    Rules: get_waitlist_admin R1, R6."""
    allowlist([])
    p = saved_profile(db, "admin@makorsha.com", True)
    p_id = p.id

    result = get_waitlist_admin(current_user=p)

    assert result is p
    assert_row_unchanged(db, p_id, "admin@makorsha.com", True)


def test_wla_g_02__admin_admitted_email_not_on_allowlist(db, allowlist):
    """WLA-G-02 — platform admin is returned even though email is not allowlisted.
    Rules: get_waitlist_admin R1, R6."""
    allowlist(["founder@makorsha.com"])
    p = saved_profile(db, "admin@makorsha.com", True)
    p_id = p.id

    result = get_waitlist_admin(current_user=p)

    assert result is p
    assert_row_unchanged(db, p_id, "admin@makorsha.com", True)


def test_wla_g_03__same_user_without_flag_refused(db, allowlist):
    """WLA-G-03 — same setup as G-02 but flag False → 403 D-NA.
    Rules: get_waitlist_admin R1, R4, R6."""
    allowlist(["founder@makorsha.com"])
    p = saved_profile(db, "admin@makorsha.com", False)
    p_id = p.id

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=p)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA
    assert_row_unchanged(db, p_id, "admin@makorsha.com", False)


def test_wla_g_04__non_admin_empty_allowlist_refused(db, allowlist):
    """WLA-G-04 — non-admin with empty allowlist → 403 (detail not asserted).
    Rules: get_waitlist_admin R2, R6."""
    allowlist([])
    p = saved_profile(db, "member@makorsha.com", False)
    p_id = p.id

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=p)

    assert exc.value.status_code == 403
    assert_row_unchanged(db, p_id, "member@makorsha.com", False)


@pytest.mark.xfail(strict=True, reason=BUG_541)
def test_wla_g_05__empty_allowlist_refusal_detail_is_d_na(db, allowlist):
    """WLA-G-05 — non-admin with empty allowlist → 403 with detail D-NA.
    Rules: get_waitlist_admin R2 [BUG-541]."""
    allowlist([])
    p = saved_profile(db, "member@makorsha.com", False)

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=p)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA


def test_wla_g_06__flag_none_blank_only_allowlist_refused(allowlist):
    """WLA-G-06 — is_platform_admin None, allowlist blank-only → 403 (detail not asserted).
    Rules: get_waitlist_admin R2, R6."""
    allowlist(["", "   "])
    obj = unsaved_profile("member@makorsha.com", None)

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert_obj_unchanged(obj, "member@makorsha.com", None)


@pytest.mark.xfail(strict=True, reason=BUG_541)
def test_wla_g_07__blank_only_allowlist_refusal_detail_is_d_na(allowlist):
    """WLA-G-07 — is_platform_admin None, blank-only allowlist → 403 with detail D-NA.
    Rules: get_waitlist_admin R2 [BUG-541]."""
    allowlist(["", "   "])
    obj = unsaved_profile("member@makorsha.com", None)

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA


def test_wla_g_08__bare_object_empty_allowlist_refused(allowlist):
    """WLA-G-08 — object without is_platform_admin, empty allowlist → 403, no AttributeError.
    Rules: get_waitlist_admin R1, R2, R6."""
    allowlist([])
    obj = bare_object()

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert_bare_unchanged(obj)


@pytest.mark.xfail(strict=True, reason=BUG_541)
def test_wla_g_09__bare_object_empty_allowlist_detail_is_d_na(allowlist):
    """WLA-G-09 — object without is_platform_admin, empty allowlist → 403 with detail D-NA.
    Rules: get_waitlist_admin R1, R2 [BUG-541]."""
    allowlist([])
    obj = bare_object()

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA


def test_wla_g_10__bare_object_not_on_allowlist_refused(allowlist):
    """WLA-G-10 — object without is_platform_admin, email not allowlisted → 403 D-NA.
    Rules: get_waitlist_admin R1, R4, R6."""
    allowlist(["founder@makorsha.com"])
    obj = bare_object()

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA
    assert_bare_unchanged(obj)


@pytest.mark.xfail(strict=True, reason=BUG_540)
@pytest.mark.parametrize(
    ("email", "entries"),
    [
        pytest.param("founder@makorsha.com", ["founder@makorsha.com"], id="WLA-G-11"),
        pytest.param("Founder@Makorsha.com", [" founder@makorsha.com "], id="WLA-G-12"),
        pytest.param(
            "founder@makorsha.com", ["ops@makorsha.com", "FOUNDER@makorsha.com"], id="WLA-G-13"
        ),
    ],
)
def test_wla_g_11_13__allowlisted_non_admin_refused(db, allowlist, email, entries):
    """WLA-G-11/12/13 — non-admin whose email matches an allowlist entry (exact,
    after trim + lower-case, second of several) is still refused 403 D-NA.
    Rules: get_waitlist_admin R3 [BUG-540]."""
    allowlist(entries)
    p = saved_profile(db, email, False)
    p_id = p.id

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=p)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA
    assert_row_unchanged(db, p_id, email, False)


@pytest.mark.parametrize(
    ("email", "entries"),
    [
        pytest.param("founder@makorsha.com.evil", ["founder@makorsha.com"], id="WLA-G-14"),
        pytest.param("founder@makorsha.com", ["makorsha.com"], id="WLA-G-15"),
        pytest.param(
            "member@makorsha.com", ["founder@makorsha.com", "ops@makorsha.com"], id="WLA-G-16"
        ),
    ],
)
def test_wla_g_14_16__non_matching_non_admin_refused(db, allowlist, email, entries):
    """WLA-G-14/15/16 — non-admin whose email does not match (prefix entry,
    domain entry, not listed) → 403 D-NA.
    Rules: get_waitlist_admin R3 (G-14, G-15), R4, R6."""
    allowlist(entries)
    p = saved_profile(db, email, False)
    p_id = p.id

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=p)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA
    assert_row_unchanged(db, p_id, email, False)


@pytest.mark.parametrize(
    ("email", "entries"),
    [
        pytest.param(None, ["founder@makorsha.com"], id="WLA-G-17"),
        pytest.param("", ["founder@makorsha.com", "", "   "], id="WLA-G-18"),
        pytest.param("   ", ["founder@makorsha.com", "   "], id="WLA-G-19"),
    ],
)
def test_wla_g_17_19__blank_email_refused(allowlist, email, entries):
    """WLA-G-17/18/19 — non-admin with email None / "" / whitespace → 403 D-NA,
    no AttributeError/TypeError; blank allowlist entries never match.
    Rules: get_waitlist_admin R5 (R2 for G-18), R6."""
    allowlist(entries)
    obj = unsaved_profile(email, False)

    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=obj)

    assert exc.value.status_code == 403
    assert exc.value.detail == D_NA
    assert_obj_unchanged(obj, email, False)
