"""Unit tests for app/utils/profile_auth.py.

Implements tests/unit/utils/profile_auth.cases.md (revision 2), one test per
case. Real Postgres session (`db` fixture) for the persisted-profile cases.
Externals mocked: none (the spec lists none). No race simulations.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.profile import Profile
from app.utils.profile_auth import profile_to_auth_dict
from tests.unit.factories import make_profile

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "EXPECTED_KEYS"
EXPECTED_KEYS = {"id", "name", "email", "timezone", "is_platform_admin"}

# Convention "P1" field values
P1_NAME = "Rahim Uddin"
P1_EMAIL = "rahim@example.com"
P1_TZ = "Asia/Dhaka"
P1_HASH = "hash-secret-xyz"


def _make_p1(db, *, is_platform_admin=False) -> Profile:
    """Convention "P1": a persisted, flushed Profile (id assigned).
    user_id is left to make_profile (any unique value)."""
    return make_profile(
        db,
        name=P1_NAME,
        email=P1_EMAIL,
        timezone=P1_TZ,
        is_platform_admin=is_platform_admin,
        hashed_password=P1_HASH,
    )


@pytest.fixture
def p1(db) -> Profile:
    return _make_p1(db)


def _p1_expected(p: Profile) -> dict:
    return {
        "id": p.id,
        "name": P1_NAME,
        "email": P1_EMAIL,
        "timezone": P1_TZ,
        "is_platform_admin": False,
    }


# Convention "NS(...)": types.SimpleNamespace with exactly the attributes listed
NS = SimpleNamespace


def _nadia() -> Profile:
    """Transient Profile of PAUTH-D-05 / D-10: no is_platform_admin argument."""
    return Profile(name="Nadia", email="nadia@example.com", timezone="Asia/Dhaka")


# --------------------------------------------------------------------------- #
# profile_to_auth_dict
# --------------------------------------------------------------------------- #


def test_pauth_d_01__persisted_profile_maps_to_public_dict(db, p1):
    """PAUTH-D-01 — a persisted profile maps to exactly the 5 public keys.
    Rules: profile_to_auth_dict R1, R2, R3."""
    result = profile_to_auth_dict(p1)

    assert isinstance(result, dict)
    assert set(result.keys()) == EXPECTED_KEYS
    assert len(result) == 5
    assert result == {
        "id": p1.id,
        "name": "Rahim Uddin",
        "email": "rahim@example.com",
        "timezone": "Asia/Dhaka",
        "is_platform_admin": False,
    }
    assert result["is_platform_admin"] is False
    assert "hashed_password" not in result
    assert "user_id" not in result
    assert "saved_stamp" not in result
    assert "hash-secret-xyz" not in result.values()


def test_pauth_d_02__fields_copied_verbatim(db):
    """PAUTH-D-02 — name/email/timezone copied exactly, no trim or case change.
    Rules: profile_to_auth_dict R2."""
    profile = Profile(
        name="  rahim UDDIN  ",
        email=" Rahim@Example.COM ",
        timezone="America/New_York",
        is_platform_admin=False,
    )

    result = profile_to_auth_dict(profile)

    assert result["name"] == "  rahim UDDIN  "
    assert result["email"] == " Rahim@Example.COM "
    assert result["timezone"] == "America/New_York"
    assert set(result.keys()) == EXPECTED_KEYS


def test_pauth_d_03__none_timezone_stays_none(db):
    """PAUTH-D-03 — a None timezone is kept as None, key still present.
    Rules: profile_to_auth_dict R2."""
    profile = Profile(
        name="Karim", email="karim@example.com", timezone=None, is_platform_admin=False
    )

    result = profile_to_auth_dict(profile)

    assert result["timezone"] is None
    assert "timezone" in result
    assert result["name"] == "Karim"
    assert result["email"] == "karim@example.com"


def test_pauth_d_04__admin_flag_true(db):
    """PAUTH-D-04 — a persisted admin profile maps is_platform_admin to True.
    Rules: profile_to_auth_dict R3."""
    p1 = _make_p1(db, is_platform_admin=True)

    result = profile_to_auth_dict(p1)

    assert result["is_platform_admin"] is True
    assert set(result.keys()) == EXPECTED_KEYS


def test_pauth_d_05__none_flag_maps_to_false(db):
    """PAUTH-D-05 — a transient profile with flag None maps to False.
    Rules: profile_to_auth_dict R3."""
    profile = _nadia()
    assert profile.is_platform_admin is None  # precondition

    result = profile_to_auth_dict(profile)

    assert result["is_platform_admin"] is False


def test_pauth_d_06__absent_flag_maps_to_false(db):
    """PAUTH-D-06 — an object without is_platform_admin maps to False, no error.
    Rules: profile_to_auth_dict R3."""
    obj = NS(id=7, name="Ghost", email="ghost@example.com", timezone="UTC")

    result = profile_to_auth_dict(obj)

    assert result["is_platform_admin"] is False
    assert result == {
        "id": 7,
        "name": "Ghost",
        "email": "ghost@example.com",
        "timezone": "UTC",
        "is_platform_admin": False,
    }


def test_pauth_d_07__truthy_non_bool_flag_is_true(db):
    """PAUTH-D-07 — flag 1 is converted to the real bool True.
    Rules: profile_to_auth_dict R3."""
    obj = NS(id=8, name="One", email="one@example.com", timezone="UTC", is_platform_admin=1)

    result = profile_to_auth_dict(obj)

    assert result["is_platform_admin"] is True


def test_pauth_d_08__falsy_non_bool_flag_is_false(db):
    """PAUTH-D-08 — flag 0 is converted to the real bool False.
    Rules: profile_to_auth_dict R3 (best-practice default, delegated by reviewer)."""
    obj = NS(id=9, name="Zero", email="zero@example.com", timezone="UTC", is_platform_admin=0)

    result = profile_to_auth_dict(obj)

    assert result["is_platform_admin"] is False


def test_pauth_d_09__persisted_profile_not_modified(db, p1):
    """PAUTH-D-09 — mapping a persisted profile leaves it and its row unchanged.
    Rules: profile_to_auth_dict R4."""
    before = (p1.name, p1.email, p1.timezone, p1.is_platform_admin, p1.hashed_password)
    p1_id = p1.id

    result = profile_to_auth_dict(p1)

    assert p1 not in db.dirty
    assert (
        p1.name, p1.email, p1.timezone, p1.is_platform_admin, p1.hashed_password
    ) == before
    db.expire_all()
    row = db.execute(select(Profile).where(Profile.id == p1_id)).scalar_one()
    assert row.name == "Rahim Uddin"
    assert row.email == "rahim@example.com"
    assert row.timezone == "Asia/Dhaka"
    assert row.is_platform_admin is False
    assert row.hashed_password == "hash-secret-xyz"
    assert result == {
        "id": p1_id,
        "name": "Rahim Uddin",
        "email": "rahim@example.com",
        "timezone": "Asia/Dhaka",
        "is_platform_admin": False,
    }


def test_pauth_d_10__transient_profile_not_modified_result_is_new_dict(db):
    """PAUTH-D-10 — flag not written back; result is an independent new dict.
    Rules: profile_to_auth_dict R4."""
    profile = _nadia()

    result = profile_to_auth_dict(profile)
    result["name"] = "Changed"

    assert profile.is_platform_admin is None
    assert profile.name == "Nadia"
    assert result["is_platform_admin"] is False
    second = profile_to_auth_dict(profile)
    assert second is not result
    assert second["name"] == "Nadia"


def test_pauth_d_11__missing_id_raises(db):
    """PAUTH-D-11 — an object without id raises AttributeError, input unchanged.
    Rules: profile_to_auth_dict Errors row (missing id)."""
    obj = NS(name="A", email="a@example.com", timezone="UTC", is_platform_admin=False)
    before = dict(vars(obj))

    with pytest.raises(AttributeError):
        profile_to_auth_dict(obj)

    assert len(vars(obj)) == 4
    assert vars(obj) == before


def test_pauth_d_12__missing_name_raises(db):
    """PAUTH-D-12 — an object without name raises AttributeError, input unchanged.
    Rules: profile_to_auth_dict Errors row (missing name)."""
    obj = NS(id=1, email="a@example.com", timezone="UTC", is_platform_admin=False)
    before = dict(vars(obj))

    with pytest.raises(AttributeError):
        profile_to_auth_dict(obj)

    assert vars(obj) == before


@pytest.mark.parametrize(
    "attrs",
    [
        pytest.param(
            {"id": 1, "name": "A", "timezone": "UTC", "is_platform_admin": False},
            id="PAUTH-D-13a-missing-email",
        ),
        pytest.param(
            {"id": 1, "name": "A", "email": "a@example.com", "is_platform_admin": False},
            id="PAUTH-D-13b-missing-timezone",
        ),
    ],
)
def test_pauth_d_13__missing_email_or_timezone_raises(db, attrs):
    """PAUTH-D-13 — an object without email / timezone raises AttributeError.
    Rules: profile_to_auth_dict Errors row (missing email, timezone)."""
    obj = NS(**attrs)
    before = dict(vars(obj))

    with pytest.raises(AttributeError):
        profile_to_auth_dict(obj)

    assert vars(obj) == before
