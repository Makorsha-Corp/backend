"""Unit tests for app/core/security.py.

Implements tests/unit/core/security.cases.md one test per case.
Pure module: no database. Only `app.core.security.utcnow` is patched (where a
case says so); bcrypt, PyJWT, hashlib and secrets run for real.
"""
# ruff: noqa: DTZ001  (prescribed by the cards: naive datetimes)
import base64
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bcrypt
import jwt
import pytest

from app.core import security
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)

# --------------------------------------------------------------------------- #
# Conventions -> constants / fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "K1 / K2" signing keys
K1 = "unit-test-secret-key-0123456789abcdef"
K2 = "another-unit-test-secret-key-0123456789"

# Convention "T0" (naive) and ts(h, m, s)
T0 = datetime(2026, 1, 1, 12, 0, 0)


def ts(h, m, s):
    return int(datetime(2026, 1, 1, h, m, s, tzinfo=timezone.utc).timestamp())


# Convention "Hashes": A72, A73, TK24 (72 UTF-8 bytes), TK25 (75 bytes)
A72 = "a" * 72
A73 = "a" * 73
TK24 = "৳" * 24
TK25 = "৳" * 25

BCRYPT_LIMIT_MSG = "Password exceeds bcrypt's 72-byte limit"


# Convention "Settings in every test": SECRET_KEY=K1, ALGORITHM=HS256,
# ACCESS_TOKEN_EXPIRE_MINUTES=15 (set on app.core.config.settings).
@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", K1)
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)


# Convention "utcnow = X": patch app.core.security.utcnow (the only external).
def patch_utcnow(value):
    return patch.object(security, "utcnow", return_value=value)


@pytest.fixture
def at_t0():
    with patch_utcnow(T0):
        yield


# Convention "NOW" / "REAL_UTCNOW" taken at test start (real clock)
@pytest.fixture
def NOW():
    return int(time.time())


@pytest.fixture
def REAL_UTCNOW():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Convention "H1 = get_password_hash('Secret-Pass-1')" -- read-only, shared per module
@pytest.fixture(scope="module")
def H1():
    return get_password_hash("Secret-Pass-1")


# Convention "peek(t)" / "header(t)" / "sign(...)" / "b64url_nopad(s)"
def peek(t):
    return jwt.decode(t, K1, algorithms=[settings.ALGORITHM], options={"verify_exp": False})


def header(t):
    return jwt.get_unverified_header(t)


def sign(claims, key=K1, alg="HS256"):
    return jwt.encode(claims, key, algorithm=alg)


def b64url_nopad(s):
    return base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()


# --------------------------------------------------------------------------- #
# create_access_token
# --------------------------------------------------------------------------- #


def test_sec_cat_01__claims_signed_with_secret(at_t0):
    """SEC-CAT-01 — token is a 3-segment HS256 JWT carrying the claims plus exp, signed with K1.
    Rules: create_access_token R1."""
    t = create_access_token({"sub": "5", "email": "a@x.com", "workspace_id": 7})
    assert isinstance(t, str)
    parts = t.split(".")
    assert len(parts) == 3 and all(parts)
    assert header(t)["alg"] == "HS256"
    p = peek(t)
    assert p["sub"] == "5"
    assert p["email"] == "a@x.com"
    assert p["workspace_id"] == 7
    assert "exp" in p
    assert set(p) == {"sub", "email", "workspace_id", "exp"}
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(t, K2, algorithms=["HS256"], options={"verify_exp": False})


def test_sec_cat_02__algorithm_from_settings(at_t0, monkeypatch):
    """SEC-CAT-02 — the configured ALGORITHM (HS512) is used to sign.
    Rules: create_access_token R1."""
    monkeypatch.setattr(settings, "ALGORITHM", "HS512")
    t = create_access_token({"sub": "5"})
    assert header(t)["alg"] == "HS512"
    assert jwt.decode(t, K1, algorithms=["HS512"], options={"verify_exp": False})["sub"] == "5"


def test_sec_cat_03__default_lifetime(at_t0):
    """SEC-CAT-03 — no expires_delta -> exp = T0 + 15 min, an int.
    Rules: create_access_token R2."""
    t = create_access_token({"sub": "5"})
    exp = peek(t)["exp"]
    assert exp == ts(12, 15, 0)
    assert isinstance(exp, int)


def test_sec_cat_04__explicit_none_uses_default(at_t0):
    """SEC-CAT-04 — expires_delta=None -> default 15 min.
    Rules: create_access_token R2."""
    t = create_access_token({"sub": "5"}, expires_delta=None)
    assert peek(t)["exp"] == ts(12, 15, 0)


def test_sec_cat_05__default_read_at_call_time(at_t0, monkeypatch):
    """SEC-CAT-05 — ACCESS_TOKEN_EXPIRE_MINUTES=30 read at call time.
    Rules: create_access_token R2."""
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    t = create_access_token({"sub": "5"})
    assert peek(t)["exp"] == ts(12, 30, 0)


def test_sec_cat_06__fractional_seconds_dropped():
    """SEC-CAT-06 — utcnow with 750000 microseconds -> exp in whole seconds.
    Rules: create_access_token R2."""
    with patch_utcnow(datetime(2026, 1, 1, 12, 0, 0, 750000)):
        t = create_access_token({"sub": "5"})
    exp = peek(t)["exp"]
    assert exp == ts(12, 15, 0)
    assert isinstance(exp, int)


def test_sec_cat_07__custom_lifetime(at_t0):
    """SEC-CAT-07 — expires_delta=2h -> exp = T0 + 2h.
    Rules: create_access_token R3."""
    t = create_access_token({"sub": "5"}, expires_delta=timedelta(hours=2))
    assert peek(t)["exp"] == ts(14, 0, 0)
    assert peek(t)["sub"] == "5"


def test_sec_cat_08__one_second_lifetime(at_t0):
    """SEC-CAT-08 — smallest positive lifetime honoured, not the default.
    Rules: create_access_token R3."""
    t = create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=1))
    assert peek(t)["exp"] == ts(12, 0, 1)


def test_sec_cat_09__negative_lifetime(at_t0):
    """SEC-CAT-09 — expires_delta=-60s -> exp = T0 - 60s.
    Rules: create_access_token R3."""
    t = create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=-60))
    assert peek(t)["exp"] == ts(11, 59, 0)


def test_sec_cat_10__negative_lifetime_already_expired(NOW):
    """SEC-CAT-10 — real clock, -60s -> exp before NOW and decode_token rejects it.
    Rules: create_access_token R3; decode_token R2."""
    t = create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=-60))
    assert peek(t)["exp"] < NOW
    assert decode_token(t) is None


@pytest.mark.xfail(
    strict=True,
    reason="BUG-501: Zero expires_delta ignored; token gets default 15-minute lifetime",
)
def test_sec_cat_11__zero_lifetime_honoured(at_t0):
    """SEC-CAT-11 — expires_delta=timedelta(0) -> exp == T0 exactly.
    Rules: create_access_token R3a [BUG-501]."""
    t = create_access_token({"sub": "5"}, expires_delta=timedelta(0))
    assert peek(t)["exp"] == ts(12, 0, 0)


def test_sec_cat_12__caller_exp_overwritten(at_t0):
    """SEC-CAT-12 — a caller-supplied exp is replaced by the computed one.
    Rules: create_access_token R4."""
    t = create_access_token({"sub": "5", "exp": 1})
    assert peek(t)["exp"] == ts(12, 15, 0)
    assert peek(t)["sub"] == "5"


def test_sec_cat_13__input_dict_not_mutated(at_t0):
    """SEC-CAT-13 — the caller's dict is left untouched (no exp added).
    Rules: create_access_token R5."""
    data = {"sub": "5", "email": "a@x.com"}
    t = create_access_token(data)
    assert data == {"sub": "5", "email": "a@x.com"}
    assert "exp" not in data
    assert isinstance(t, str)


def test_sec_cat_14__caller_exp_untouched(at_t0):
    """SEC-CAT-14 — caller's own exp stays 1 in their dict; token gets computed exp.
    Rules: create_access_token R4, R5."""
    data = {"sub": "5", "exp": 1}
    t = create_access_token(data)
    assert data == {"sub": "5", "exp": 1}
    assert peek(t)["exp"] == ts(12, 15, 0)


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"sub": "5", "when": datetime(2026, 1, 1)}, id="SEC-CAT-15"),
        pytest.param({"sub": "5", "roles": {"admin"}}, id="SEC-CAT-16"),
    ],
)
def test_sec_cat_15_16__non_json_claim_raises(at_t0, claims):
    """SEC-CAT-15 / SEC-CAT-16 — non-JSON-serialisable claim (datetime, set) raises TypeError.
    Rules: create_access_token R6; Errors row 1."""
    with pytest.raises(TypeError):
        create_access_token(claims)


# --------------------------------------------------------------------------- #
# verify_password
# --------------------------------------------------------------------------- #


def test_sec_vp_01__correct_password(H1):
    """SEC-VP-01 — correct password returns True (is True).
    Rules: verify_password R3."""
    assert verify_password("Secret-Pass-1", H1) is True


@pytest.mark.parametrize(
    "plain",
    [
        pytest.param("secret-pass-1", id="SEC-VP-02"),
        pytest.param("Secret-Pass-1 ", id="SEC-VP-03"),
        pytest.param("", id="SEC-VP-04"),
    ],
)
def test_sec_vp_02_04__wrong_password(H1, plain):
    """SEC-VP-02 / 03 / 04 — wrong case, trailing space, empty -> False, no raise.
    Rules: verify_password R3."""
    assert verify_password(plain, H1) is False


@pytest.mark.parametrize(
    "hashed",
    [pytest.param("", id="SEC-VP-05"), pytest.param(None, id="SEC-VP-06")],
)
def test_sec_vp_05_06__empty_hash(hashed):
    """SEC-VP-05 / 06 — empty or None stored hash -> False, no raise.
    Rules: verify_password R1."""
    assert verify_password("Secret-Pass-1", hashed) is False


def test_sec_vp_07__long_password_empty_hash():
    """SEC-VP-07 — 73-byte password against ''/None -> False, no raise (BUG-500 guard).
    Rules: verify_password R1."""
    assert verify_password(A73, "") is False
    assert verify_password(A73, None) is False


def test_sec_vp_08__malformed_hash():
    """SEC-VP-08 — non-bcrypt hash string -> False, no raise.
    Rules: verify_password R4."""
    assert verify_password("Secret-Pass-1", "garbage") is False


def test_sec_vp_09__sha256_hash_not_accepted():
    """SEC-VP-09 — a sha256 hex digest of the password is not a bcrypt hash -> False.
    Rules: verify_password R4."""
    S = hashlib.sha256(b"Secret-Pass-1").hexdigest()
    assert verify_password("Secret-Pass-1", S) is False


def test_sec_vp_10__bytes_hash_accepted(H1):
    """SEC-VP-10 — hash passed as bytes -> True for the right password.
    Rules: verify_password R5."""
    assert verify_password("Secret-Pass-1", H1.encode()) is True


def test_sec_vp_11__bytes_hash_wrong_password(H1):
    """SEC-VP-11 — hash as bytes, wrong password -> False.
    Rules: verify_password R5."""
    assert verify_password("secret-pass-1", H1.encode()) is False


def test_sec_vp_12__exactly_72_bytes():
    """SEC-VP-12 — 72-byte password verifies; 71-byte prefix does not; no raise.
    Rules: verify_password R2, R3."""
    HA72 = get_password_hash(A72)
    assert verify_password(A72, HA72) is True
    assert verify_password("a" * 71, HA72) is False


def test_sec_vp_13__72_utf8_bytes_multibyte():
    """SEC-VP-13 — 24 x '৳' (72 UTF-8 bytes) verifies.
    Rules: verify_password R2, R3."""
    HTK24 = get_password_hash(TK24)
    assert verify_password(TK24, HTK24) is True


_BUG_500 = "BUG-500: Over-long login password reveals whether the email is registered"


@pytest.mark.xfail(strict=True, reason=_BUG_500)
def test_sec_vp_14__73_bytes_returns_false(H1):
    """SEC-VP-14 — 73-byte password -> False, no raise.
    Rules: verify_password R2 [BUG-500]."""
    assert verify_password(A73, H1) is False


@pytest.mark.xfail(strict=True, reason=_BUG_500)
def test_sec_vp_15__75_utf8_bytes_returns_false(H1):
    """SEC-VP-15 — 25 x '৳' (75 bytes) -> False, no raise.
    Rules: verify_password R2 [BUG-500]."""
    assert verify_password(TK25, H1) is False


@pytest.mark.xfail(strict=True, reason=_BUG_500)
def test_sec_vp_16__no_silent_truncation():
    """SEC-VP-16 — 73-byte password vs hash of its first 72 bytes -> False, no raise.
    Rules: verify_password R2 [BUG-500]."""
    HA72 = get_password_hash(A72)
    assert verify_password(A73, HA72) is False


@pytest.mark.xfail(strict=True, reason=_BUG_500)
def test_sec_vp_17__long_password_malformed_hash():
    """SEC-VP-17 — 73-byte password vs 'garbage' -> False, no raise.
    Rules: verify_password R2 [BUG-500]."""
    assert verify_password(A73, "garbage") is False


@pytest.mark.xfail(strict=True, reason=_BUG_500)
def test_sec_vp_18__long_password_bytes_hash(H1):
    """SEC-VP-18 — 73-byte password vs bytes hash -> False, no raise.
    Rules: verify_password R2 [BUG-500], R5."""
    assert verify_password(A73, H1.encode()) is False


# --------------------------------------------------------------------------- #
# get_password_hash
# --------------------------------------------------------------------------- #


def test_sec_gph_01__bcrypt_hash_shape():
    """SEC-GPH-01 — 60-char $2b$12$ bcrypt string that verifies.
    Rules: get_password_hash R1."""
    h = get_password_hash("Secret-Pass-1")
    assert isinstance(h, str)
    assert len(h) == 60
    assert h.startswith("$2b$12$")
    assert verify_password("Secret-Pass-1", h) is True
    assert bcrypt.checkpw(b"Secret-Pass-1", h.encode()) is True


def test_sec_gph_02__exactly_72_bytes():
    """SEC-GPH-02 — 72-byte password is hashed.
    Rules: get_password_hash R2."""
    h = get_password_hash(A72)
    assert isinstance(h, str)
    assert len(h) == 60
    assert h.startswith("$2b$12$")
    assert bcrypt.checkpw(A72.encode(), h.encode()) is True


@pytest.mark.parametrize(
    "password",
    [pytest.param(A73, id="SEC-GPH-03"), pytest.param(TK25, id="SEC-GPH-05")],
)
def test_sec_gph_03_05__over_72_bytes_rejected(password):
    """SEC-GPH-03 / 05 — > 72 UTF-8 bytes (73 ASCII / 25 chars = 75 bytes) raises ValueError.
    Rules: get_password_hash R2; Errors row 1."""
    with pytest.raises(ValueError) as exc:
        get_password_hash(password)
    assert str(exc.value) == BCRYPT_LIMIT_MSG


def test_sec_gph_04__72_utf8_bytes_multibyte():
    """SEC-GPH-04 — 24 x '৳' (72 bytes) is hashed.
    Rules: get_password_hash R2."""
    h = get_password_hash(TK24)
    assert isinstance(h, str)
    assert len(h) == 60
    assert bcrypt.checkpw(TK24.encode("utf-8"), h.encode()) is True


def test_sec_gph_06__fresh_salt_each_call():
    """SEC-GPH-06 — two hashes of the same password differ (salt) and both verify.
    Rules: get_password_hash R3."""
    h1 = get_password_hash("Secret-Pass-1")
    h2 = get_password_hash("Secret-Pass-1")
    assert h1 != h2
    assert h1[:29] != h2[:29]
    assert verify_password("Secret-Pass-1", h1) is True
    assert verify_password("Secret-Pass-1", h2) is True


def test_sec_gph_07__plaintext_not_in_hash():
    """SEC-GPH-07 — the plaintext does not appear in the hash.
    Rules: get_password_hash R4."""
    h = get_password_hash("Plaintext99")
    assert "Plaintext99" not in h
    assert len(h) == 60


def test_sec_gph_08__empty_password_hashed():
    """SEC-GPH-08 — empty password is hashed and only '' verifies.
    Rules: get_password_hash R5."""
    h = get_password_hash("")
    assert isinstance(h, str)
    assert len(h) == 60
    assert h.startswith("$2b$12$")
    assert bcrypt.checkpw(b"", h.encode()) is True
    assert verify_password("a", h) is False


# --------------------------------------------------------------------------- #
# create_refresh_token
# --------------------------------------------------------------------------- #


def test_sec_crt_01__raw_token_shape():
    """SEC-CRT-01 — raw token is 86 url-safe chars, no padding, 64 bytes of entropy.
    Rules: create_refresh_token R1."""
    result = create_refresh_token()
    assert isinstance(result, tuple)
    assert len(result) == 2
    raw = result[0]
    assert isinstance(raw, str)
    assert len(raw) == 86
    assert re.fullmatch(r"[A-Za-z0-9_-]{86}", raw)
    assert "=" not in raw
    assert len(base64.urlsafe_b64decode(raw + "==")) == 64


def test_sec_crt_02__hash_is_sha256_of_raw():
    """SEC-CRT-02 — second element is the sha256 hex of the raw token.
    Rules: create_refresh_token R2."""
    raw, h = create_refresh_token()
    assert h == hash_refresh_token(raw)
    assert h == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", h)


def test_sec_crt_03__tokens_unique():
    """SEC-CRT-03 — 20 calls give 20 distinct raw tokens and 20 distinct hashes.
    Rules: create_refresh_token R3."""
    pairs = [create_refresh_token() for _ in range(20)]
    assert len({raw for raw, _ in pairs}) == 20
    assert len({h for _, h in pairs}) == 20


# --------------------------------------------------------------------------- #
# hash_refresh_token
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "digest"),
    [
        pytest.param("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", id="SEC-HRT-01"),
        pytest.param("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", id="SEC-HRT-02"),
    ],
)
def test_sec_hrt_01_02__known_sha256_vectors(raw, digest):
    """SEC-HRT-01 / 02 — known sha256 test vectors.
    Rules: hash_refresh_token R1."""
    assert hash_refresh_token(raw) == digest


def test_sec_hrt_03__deterministic():
    """SEC-HRT-03 — same input twice -> same digest, equal to hashlib's.
    Rules: hash_refresh_token R1, R2."""
    a = hash_refresh_token("refresh-token-xyz")
    b = hash_refresh_token("refresh-token-xyz")
    assert a == b
    assert a == hashlib.sha256(b"refresh-token-xyz").hexdigest()


def test_sec_hrt_04__distinct_inputs_distinct_digests():
    """SEC-HRT-04 — abc / abd / ABC give pairwise different digests.
    Rules: hash_refresh_token R2."""
    x, y, z = hash_refresh_token("abc"), hash_refresh_token("abd"), hash_refresh_token("ABC")
    assert x != y
    assert x != z
    assert y != z


def test_sec_hrt_05__non_ascii_utf8():
    """SEC-HRT-05 — non-ASCII input hashed as UTF-8, no raise.
    Rules: hash_refresh_token R3."""
    h = hash_refresh_token("৳ঢাকা")
    assert h == hashlib.sha256("৳ঢাকা".encode()).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", h)


# --------------------------------------------------------------------------- #
# decode_token  (all relative to the real clock NOW)
# --------------------------------------------------------------------------- #


def test_sec_dt_01__round_trip(NOW):
    """SEC-DT-01 — a freshly created token decodes to its claims plus int exp > NOW.
    Rules: decode_token R1."""
    t = create_access_token({"sub": "5", "email": "a@x.com", "workspace_id": 7})
    p = decode_token(t)
    assert isinstance(p, dict)
    assert set(p) == {"sub", "email", "workspace_id", "exp"}
    assert p["sub"] == "5"
    assert p["email"] == "a@x.com"
    assert p["workspace_id"] == 7
    assert isinstance(p["exp"], int)
    assert p["exp"] > NOW


def test_sec_dt_02__expired_token_none(REAL_UTCNOW):
    """SEC-DT-02 — token minted 16 min ago (15 min lifetime) -> None.
    Rules: decode_token R2."""
    with patch_utcnow(REAL_UTCNOW - timedelta(minutes=16)):
        t = create_access_token({"sub": "5"})
    assert decode_token(t) is None


def test_sec_dt_03__not_yet_expired(REAL_UTCNOW):
    """SEC-DT-03 — token minted 14 min ago -> still valid.
    Rules: decode_token R2."""
    with patch_utcnow(REAL_UTCNOW - timedelta(minutes=14)):
        t = create_access_token({"sub": "5"})
    p = decode_token(t)
    assert p["sub"] == "5"


def test_sec_dt_04__zero_leeway(NOW):
    """SEC-DT-04 — exp 5 s in the past -> None (zero leeway).
    Rules: decode_token R2."""
    t = sign({"sub": "5", "exp": NOW - 5})
    assert decode_token(t) is None


def test_sec_dt_05__future_exp_accepted(NOW):
    """SEC-DT-05 — exp 60 s ahead -> payload returned exactly.
    Rules: decode_token R2."""
    t = sign({"sub": "5", "exp": NOW + 60})
    assert decode_token(t) == {"sub": "5", "exp": NOW + 60}


def test_sec_dt_06__wrong_key(NOW):
    """SEC-DT-06 — signed with K2 -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600}, key=K2)
    assert decode_token(t) is None


def test_sec_dt_07__key_read_at_call_time(monkeypatch):
    """SEC-DT-07 — token from K1, SECRET_KEY switched to K2 -> None.
    Rules: decode_token R3."""
    t = create_access_token({"sub": "5"})
    monkeypatch.setattr(settings, "SECRET_KEY", K2)
    assert decode_token(t) is None


def test_sec_dt_08__tampered_payload(NOW):
    """SEC-DT-08 — original decodes; payload swapped under original signature -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600})
    seg = t.split(".")
    forged = seg[0] + "." + b64url_nopad(json.dumps({"sub": "1", "exp": NOW + 3600})) + "." + seg[2]
    assert decode_token(t)["sub"] == "5"
    assert decode_token(forged) is None


def test_sec_dt_09__foreign_signature(NOW):
    """SEC-DT-09 — header+payload of t with the signature of a K2 token -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600})
    t2 = sign({"sub": "5", "exp": NOW + 3600}, key=K2)
    forged = ".".join(t.split(".")[:2]) + "." + t2.split(".")[2]
    assert decode_token(forged) is None


def test_sec_dt_10__malformed_tokens(NOW):
    """SEC-DT-10 — 'abc', '', 'a.b' and a token missing its signature segment -> None each.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600})
    assert decode_token("abc") is None
    assert decode_token("") is None
    assert decode_token("a.b") is None
    assert decode_token(".".join(t.split(".")[:2])) is None


def test_sec_dt_11__algorithm_mismatch(NOW):
    """SEC-DT-11 — HS512 token while ALGORITHM=HS256 -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600}, key=K1, alg="HS512")
    assert decode_token(t) is None


def test_sec_dt_12__alg_none_rejected(NOW):
    """SEC-DT-12 — hand-built unsigned 'alg: none' token -> None.
    Rules: decode_token R3."""
    t = (
        b64url_nopad('{"alg":"none","typ":"JWT"}')
        + "."
        + b64url_nopad(json.dumps({"sub": "5", "exp": NOW + 3600}))
        + "."
    )
    assert decode_token(t) is None


def test_sec_dt_13__non_numeric_exp():
    """SEC-DT-13 — exp = 'tomorrow' -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": "tomorrow"})
    assert decode_token(t) is None


def test_sec_dt_14__future_iat(NOW):
    """SEC-DT-14 — iat 10 min in the future -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600, "iat": NOW + 600})
    assert decode_token(t) is None


def test_sec_dt_15__future_nbf(NOW):
    """SEC-DT-15 — nbf 10 min in the future -> None.
    Rules: decode_token R3."""
    t = sign({"sub": "5", "exp": NOW + 3600, "nbf": NOW + 600})
    assert decode_token(t) is None


def test_sec_dt_16__past_iat_nbf_accepted(NOW):
    """SEC-DT-16 — iat/nbf in the past -> payload equal to the claims.
    Rules: decode_token R3, R5."""
    claims = {"sub": "5", "exp": NOW + 3600, "iat": NOW - 60, "nbf": NOW - 60}
    t = sign(claims)
    assert decode_token(t) == claims


@pytest.mark.xfail(strict=True, reason="BUG-502: Signed access token without `exp` never expires")
def test_sec_dt_17__missing_exp_rejected():
    """SEC-DT-17 — correctly signed token with no exp -> None.
    Rules: decode_token R4 [BUG-502]."""
    t = sign({"sub": "1"})
    assert decode_token(t) is None


def test_sec_dt_18__no_sub_extra_claims(NOW):
    """SEC-DT-18 — no sub required; extra claims returned unchanged.
    Rules: decode_token R5."""
    claims = {"exp": NOW + 3600, "role": "admin", "tags": ["a", "b"]}
    t = sign(claims)
    assert decode_token(t) == claims
