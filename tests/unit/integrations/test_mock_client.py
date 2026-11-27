"""Unit tests for app/integrations/sslcommerz/mock_client.py.

Implements tests/unit/integrations/mock_client.cases.md (revision 2), one test
per case. Pure Python module: no database, no externals mocked, no time
patching. Only `settings.SECRET_KEY`, `settings.BACKEND_BASE_URL` and
`settings.API_V1_STR` are monkeypatched (spec Overview).

TODO-001 (reviewer): the mock will be removed or upgraded later and must be
gone or non-production-only (default off) before launch. When that happens,
retire or rewrite this file together with mock_client.spec.md / cases.md.
"""
# ruff: noqa: FURB157  (prescribed by the cards: Decimal("...") literals)
import base64
import hashlib
import hmac
import json
import re
from decimal import Decimal

import pytest

from app.core.config import settings
from app.integrations.sslcommerz.client import (
    InitSessionRequest,
    InitSessionResult,
    ValidationResult,
)
from app.integrations.sslcommerz.mock_client import MockSSLCommerzClient, _sign

# --------------------------------------------------------------------------- #
# Conventions -> constants / helpers
# --------------------------------------------------------------------------- #

BUG_580 = "BUG-580: Mock gateway cannot answer a lookup by tran_id alone"
BUG_581 = "BUG-581: Malformed val_id crashes validation (500) instead of being rejected"
BUG_582 = (
    "BUG-582: IPN with non-ASCII / non-string verify_sign crashes (500) "
    "instead of failing the signature check"
)
BUG_583 = (
    "BUG-583: Mock val_id tokens are malleable: non-canonical encodings of a "
    "signed payload are accepted"
)

# Convention "Settings": K1 / K2 and URL settings
K1 = "unit-test-secret-K1"
K2 = "unit-test-secret-K2"
BASE_URL = "http://api.test:9000"
API_V1 = "/api/v9"


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Convention "Settings": monkeypatched on app.core.config.settings in every test."""
    monkeypatch.setattr(settings, "SECRET_KEY", K1)
    monkeypatch.setattr(settings, "BACKEND_BASE_URL", BASE_URL)
    monkeypatch.setattr(settings, "API_V1_STR", API_V1)
    return monkeypatch


def set_key(monkeypatch, key):
    monkeypatch.setattr(settings, "SECRET_KEY", key)


# Convention "H(key, msg)"
def H(key, msg):
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


# Convention "ENC(obj)" / "TOK(obj, sig)"
def ENC(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def TOK(obj, sig):
    return ENC(obj) + "." + sig


# Convention "T1" / "T2"
T1 = "TXN-ABC-001"
T2 = "TXN-XYZ-002"

# Convention "P1" / "S1"
P1 = {"tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 0}
S1 = H(K1, "VALID|TXN-ABC-001|10.00|BDT|0")


# Convention "mint(inst, ...)"
def mint(inst, tran_id, amount, status, currency="BDT", risk_level=0):
    return inst.build_val_id(
        tran_id=tran_id, amount=amount, currency=currency, status=status, risk_level=risk_level
    )


# Convention "INV" / "UNATT(t)"
INV = ValidationResult(status="INVALID_TRANSACTION", tran_id="")


def UNATT(t):
    return ValidationResult(status="UNATTEMPTED", tran_id=t)


# Convention "VKEY"
VKEY = "status,tran_id,amount,currency,risk_level"

# Convention "REQ(tran_id, **overrides)" (REQ_KW of client.cases.md)
REQ_KW = {
    "tran_id": "TXN-0001",
    "amount": Decimal("10.005"),
    "currency": "BDT",
    "success_url": "https://app.example/pay/success",
    "fail_url": "https://app.example/pay/fail",
    "cancel_url": "https://app.example/pay/cancel",
    "ipn_url": "https://api.example/payments/ipn",
    "cus_name": "Rahim Uddin",
    "cus_email": "rahim@example.com",
    "cus_phone": "01700000000",
}


def REQ(tran_id, **overrides):
    return InitSessionRequest(**{**REQ_KW, "tran_id": tran_id, **overrides})


# Convention "SK(t)"
def SK(t):
    return base64.urlsafe_b64encode(hashlib.sha256(t.encode("utf-8")).digest()).decode().rstrip("=")


# Convention "MAL": malformed-payload set
Z64 = "0" * 64
MAL = [
    pytest.param(TOK({}, Z64), id="empty-object"),
    pytest.param(TOK({"status": "VALID"}, Z64), id="status-only"),
    pytest.param(TOK([1], Z64), id="list"),
    pytest.param(TOK(None, Z64), id="null"),
    pytest.param(TOK(1, Z64), id="number"),
    pytest.param(TOK({k: v for k, v in P1.items() if k != "risk_level"}, Z64), id="no-risk-level"),
    pytest.param("e30=.x", id="literal-e30"),
]

# Convention "NAS": non-ASCII signature
NAS = ENC(P1) + "." + "é" + S1[1:]

# Convention "BAD_AMT"
BAD_AMT = TOK(
    {"tran_id": T1, "amount": "abc", "currency": "BDT", "status": "VALID", "risk_level": 0},
    H(K1, "VALID|TXN-ABC-001|abc|BDT|0"),
)


# Convention "FORM(r)"
def FORM(r):
    return {
        "status": r.status,
        "tran_id": r.tran_id,
        "amount": str(r.amount),
        "currency": r.currency,
        "risk_level": str(r.risk_level),
        "verify_sign": r.verify_sign,
        "val_id": r.val_id,
        "verify_key": r.verify_key,
    }


# Convention "F1"
F1 = {
    "status": "VALID", "tran_id": T1, "amount": "10.00", "currency": "BDT",
    "risk_level": "0", "verify_sign": S1, "val_id": "VAL-ANY", "verify_key": VKEY,
}

SIGNED = ["status", "tran_id", "amount", "currency", "risk_level"]


def _decode_part(tok):
    return json.loads(base64.urlsafe_b64decode(tok.rsplit(".", 1)[0].encode()))


# Convention "E" = ENC(P1) (124 chars, ends "fQ==")
E = ENC(P1)
assert E.endswith("fQ==") and len(E) == 124  # guard: the NCB/MD inputs rely on this layout

# Invalid-token inputs of MOCK-DEC-02/03/04 (reused by MOCK-VAL-05).
# Entries that need the current key/instance are built lazily via a callable.
DEC_02_INPUTS = [
    pytest.param(lambda a, mp: "", id="empty"),
    pytest.param(lambda a, mp: "abcdef", id="no-dot"),
    pytest.param(lambda a, mp: ENC(P1) + S1, id="dot-removed"),
]
DEC_03_INPUTS = [
    pytest.param(lambda a, mp: "a." + S1, id="undecodable-base64"),
    pytest.param(lambda a, mp: "!!!.abc", id="bang-abc"),
    pytest.param(lambda a, mp: E[:-2] + "." + S1, id="incorrect-padding"),
    pytest.param(
        lambda a, mp: base64.urlsafe_b64encode(b"\xff\xfe\xfd").decode() + "." + S1, id="not-utf8"
    ),
    pytest.param(lambda a, mp: base64.urlsafe_b64encode(b"not json").decode() + "." + S1, id="not-json"),
]

# Convention "MD_OK": multi-dot tokens accepted today ([BUG-583] R3a)
MD_OK = [
    pytest.param(lambda a, mp: E + ".x." + S1, id="E.x.S1"),
    pytest.param(lambda a, mp: E + ".." + S1, id="E..S1"),
]
# Convention "MD_REJ": multi-dot tokens rejected today and after the fix
MD_REJ = [
    pytest.param(lambda a, mp: E + "." + S1 + ".", id="E.S1."),
    pytest.param(lambda a, mp: E + "." + S1 + ".x", id="E.S1.x"),
    pytest.param(lambda a, mp: "a.b.c", id="a.b.c"),
]


def _dash_to_plus(a, mp):
    tok_dash = mint(a, "TXN->>>?", Decimal("10.00"), "VALID")
    return tok_dash.replace("-", "+")


def _underscore_to_slash(a, mp):
    enc_us, sig_us = mint(a, "TXN-??", Decimal("10.00"), "VALID").split(".")
    return enc_us.replace("_", "/") + "." + sig_us


# Convention "NCB": non-canonical base64 set ([BUG-583] R3b); the first four rows are built from P1
NCB_P1 = [
    pytest.param(lambda a, mp: E[:10] + "\n" + E[10:] + "." + S1, id="newline"),
    pytest.param(lambda a, mp: E[:10] + " " + E[10:] + "." + S1, id="space"),
    pytest.param(lambda a, mp: E + "AAAA" + "." + S1, id="data-after-padding"),
    pytest.param(lambda a, mp: E[:-3] + "R==" + "." + S1, id="low-bits"),
]
NCB = NCB_P1 + [
    pytest.param(_dash_to_plus, id="dash-to-plus"),
    pytest.param(_underscore_to_slash, id="underscore-to-slash"),
]

# Convention "NCJ": non-canonical JSON set (R3b, still accepted)
NCJ = [
    pytest.param(base64.urlsafe_b64encode(json.dumps(P1).encode()).decode() + "." + S1, id="default-separators"),
    pytest.param(
        ENC({"risk_level": 0, "status": "VALID", "currency": "BDT", "amount": "10.00", "tran_id": T1}) + "." + S1,
        id="reversed-keys",
    ),
    pytest.param(ENC({**P1, "extra": "x"}) + "." + S1, id="extra-key"),
]


def _tampered(a, mp):
    tok = mint(a, T1, Decimal("500.00"), "VALID")
    sig = tok.rsplit(".", 1)[1]
    return TOK({**P1, "amount": "5.00"}, sig)


def _other_key(a, mp):
    set_key(mp, K2)
    tok = mint(a, T1, Decimal("10.00"), "VALID")
    set_key(mp, K1)
    return tok


DEC_04_INPUTS = [
    pytest.param(_tampered, id="tampered-amount"),
    pytest.param(lambda a, mp: ENC(P1) + ".", id="empty-signature"),
    pytest.param(lambda a, mp: TOK(P1, Z64), id="zero-signature"),
    pytest.param(lambda a, mp: TOK(P1, S1.upper()), id="uppercase-signature"),
    pytest.param(_other_key, id="minted-with-K2"),
]


# --------------------------------------------------------------------------- #
# _sign(payload)
# --------------------------------------------------------------------------- #

def test_mock_sign_01__signature_is_hmac_hex():
    """MOCK-SIGN-01 — _sign(P1) returns the lowercase hex HMAC-SHA256 S1.
    Rules: _sign R1."""
    result = _sign(P1)
    assert isinstance(result, str)
    assert result == S1
    assert re.fullmatch(r"[0-9a-f]{64}", result)


def test_mock_sign_02__non_ascii_key_utf8(mock_settings):
    """MOCK-SIGN-02 — a non-ASCII SECRET_KEY is UTF-8 encoded.
    Rules: _sign R1."""
    set_key(mock_settings, "clé-secrète-ü")
    assert _sign(P1) == H("clé-secrète-ü", "VALID|TXN-ABC-001|10.00|BDT|0")


def test_mock_sign_03__extra_keys_ignored():
    """MOCK-SIGN-03 — keys outside the five signed fields do not change the signature.
    Rules: _sign R2."""
    assert _sign({**P1, "val_id": "VAL-9", "foo": 1, "verify_key": "x"}) == S1


@pytest.mark.parametrize(
    ("field", "new"),
    [
        pytest.param("status", "FAILED", id="status"),
        pytest.param("tran_id", T2, id="tran_id"),
        pytest.param("amount", "11.00", id="amount"),
        pytest.param("currency", "USD", id="currency"),
        pytest.param("risk_level", 1, id="risk_level"),
    ],
)
def test_mock_sign_04__each_signed_field_changes_signature(field, new):
    """MOCK-SIGN-04 — changing any one signed field changes the signature, field order fixed.
    Rules: _sign R1, R2."""
    payload = {**P1, field: new}
    result = _sign(payload)
    assert result != S1
    msg = "|".join(str(payload[f]) for f in SIGNED)
    assert result == H(K1, msg)


def test_mock_sign_05__values_stringified():
    """MOCK-SIGN-05 — risk_level 0 and "0" sign identically.
    Rules: _sign R3."""
    a = _sign(P1)
    b = _sign({**P1, "risk_level": "0"})
    assert a == b


def test_mock_sign_06__amount_not_normalised():
    """MOCK-SIGN-06 — "10.00" and "10.0" sign differently.
    Rules: _sign R3."""
    a = _sign(P1)
    b = _sign({**P1, "amount": "10.0"})
    assert a != b
    assert b == H(K1, "VALID|TXN-ABC-001|10.0|BDT|0")


def test_mock_sign_07__none_stringified():
    """MOCK-SIGN-07 — a None value is signed as "None".
    Rules: _sign R3."""
    assert _sign({**P1, "currency": None}) == H(K1, "VALID|TXN-ABC-001|10.00|None|0")


def test_mock_sign_08__key_read_at_call_time(mock_settings):
    """MOCK-SIGN-08 — SECRET_KEY is read at call time.
    Rules: _sign R4."""
    s1 = _sign(P1)
    set_key(mock_settings, K2)
    result = _sign(P1)
    assert result != s1
    assert result == H(K2, "VALID|TXN-ABC-001|10.00|BDT|0")


@pytest.mark.parametrize("missing", [pytest.param(f, id=f) for f in SIGNED])
def test_mock_sign_09__missing_key_raises_keyerror(missing):
    """MOCK-SIGN-09 — a missing signed field raises KeyError naming it.
    Rules: _sign Errors row 1."""
    payload = {k: v for k, v in P1.items() if k != missing}
    with pytest.raises(KeyError) as exc:
        _sign(payload)
    assert exc.value.args[0] == missing


@pytest.mark.parametrize(
    "value",
    [pytest.param([1, 2], id="list"), pytest.param(None, id="none"), pytest.param(42, id="int")],
)
def test_mock_sign_10__non_mapping_raises_typeerror(value):
    """MOCK-SIGN-10 — a non-mapping payload raises TypeError.
    Rules: _sign Errors row 2."""
    with pytest.raises(TypeError):
        _sign(value)


# --------------------------------------------------------------------------- #
# init_session(req)
# --------------------------------------------------------------------------- #

def test_mock_init_01__success_with_key_and_url():
    """MOCK-INIT-01 — init_session returns SUCCESS, a derived session key and the mock-gateway URL.
    Rules: init_session R1, R2, R3."""
    A = MockSSLCommerzClient()
    r = A.init_session(REQ("TXN-ABC-001"))
    assert isinstance(r, InitSessionResult)
    assert r.status == "SUCCESS"
    assert r.failed_reason is None
    assert r.session_key == SK("TXN-ABC-001")
    assert len(r.session_key) == 43
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", r.session_key)
    assert r.gateway_page_url == "http://api.test:9000/api/v9/payments/mock-gateway/TXN-ABC-001"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"amount": Decimal("0")}, id="zero-amount"),
        pytest.param(
            {
                "amount": Decimal("-5.00"), "currency": "", "success_url": "", "fail_url": "",
                "cancel_url": "", "ipn_url": "", "cus_name": "", "cus_email": "", "cus_phone": "",
            },
            id="negative-and-empty",
        ),
    ],
)
def test_mock_init_02__other_fields_ignored(overrides):
    """MOCK-INIT-02 — fields other than tran_id do not affect the result.
    Rules: init_session R1."""
    A = MockSSLCommerzClient()
    r = A.init_session(REQ(T1, **overrides))
    assert r.status == "SUCCESS"
    assert r.failed_reason is None
    assert r.session_key == SK(T1)
    assert r.gateway_page_url == "http://api.test:9000/api/v9/payments/mock-gateway/TXN-ABC-001"


def test_mock_init_03__session_key_depends_only_on_tran_id():
    """MOCK-INIT-03 — session key is a pure function of tran_id, across instances.
    Rules: init_session R2."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    k1 = A.init_session(REQ(T1)).session_key
    k2 = B.init_session(REQ(T1, amount=Decimal("99.00"), currency="USD")).session_key
    k3 = A.init_session(REQ(T2)).session_key
    k4 = A.init_session(REQ("")).session_key
    assert k1 == k2 == SK(T1)
    assert k3 == SK(T2)
    assert k3 != SK(T1)
    assert k4 == SK("")
    assert len(k4) == 43


def test_mock_init_04__url_not_encoded(mock_settings):
    """MOCK-INIT-04 — URL built from settings with the raw tran_id (no URL-encoding).
    Rules: init_session R3."""
    mock_settings.setattr(settings, "BACKEND_BASE_URL", "https://pay.example.org")
    mock_settings.setattr(settings, "API_V1_STR", "/v2")
    A = MockSSLCommerzClient()
    r = A.init_session(REQ("a b/c?d=é"))
    assert r.gateway_page_url == "https://pay.example.org/v2/payments/mock-gateway/a b/c?d=é"
    assert r.session_key == SK("a b/c?d=é")


# --------------------------------------------------------------------------- #
# build_val_id(...)
# --------------------------------------------------------------------------- #

def test_mock_bvi_01__token_format():
    """MOCK-BVI-01 — token = compact urlsafe-base64 JSON + "." + HMAC signature.
    Rules: build_val_id R1, R2."""
    A = MockSSLCommerzClient()
    tok = A.build_val_id(tran_id=T1, amount=Decimal("10.00"), currency="BDT", status="VALID", risk_level=1)
    assert isinstance(tok, str)
    payload = {"tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 1}
    assert tok == ENC(payload) + "." + H(K1, "VALID|TXN-ABC-001|10.00|BDT|1")
    raw = base64.urlsafe_b64decode(tok.rsplit(".", 1)[0].encode())
    assert raw == (
        b'{"tran_id":"TXN-ABC-001","amount":"10.00","currency":"BDT","status":"VALID","risk_level":1}'
    )


@pytest.mark.parametrize(
    ("tran_id", "char"),
    [pytest.param("TXN->>>?", "-", id="dash"), pytest.param("TXN-??", "_", id="underscore")],
)
def test_mock_bvi_02__urlsafe_alphabet_with_padding(tran_id, char):
    """MOCK-BVI-02 — encoded part uses the URL-safe alphabet and keeps padding.
    Rules: build_val_id R1."""
    A = MockSSLCommerzClient()
    tok = mint(A, tran_id, Decimal("10.00"), "VALID")
    encoded = tok.split(".")[0]
    assert encoded == ENC(
        {"tran_id": tran_id, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 0}
    )
    assert encoded.endswith("=")
    assert char in encoded
    assert "+" not in encoded
    assert "/" not in encoded


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param(Decimal("1E+2"), id="1E+2"),
        pytest.param(Decimal("10.00"), id="10.00"),
        pytest.param(Decimal("10.0"), id="10.0"),
    ],
)
def test_mock_bvi_03__amount_str_risk_int(amount):
    """MOCK-BVI-03 — amount is stored as str(amount), risk_level as a JSON int.
    Rules: build_val_id R1."""
    A = MockSSLCommerzClient()
    payload = _decode_part(mint(A, T1, amount, "VALID"))
    assert payload["amount"] == str(amount)
    assert isinstance(payload["amount"], str)
    assert payload["risk_level"] == 0
    assert type(payload["risk_level"]) is int


def test_mock_bvi_04__risk_level_defaults_to_zero():
    """MOCK-BVI-04 — omitted risk_level is 0.
    Rules: build_val_id R3."""
    A = MockSSLCommerzClient()
    t_default = A.build_val_id(tran_id=T1, amount=Decimal("10.00"), currency="BDT", status="VALID")
    t_zero = A.build_val_id(tran_id=T1, amount=Decimal("10.00"), currency="BDT", status="VALID", risk_level=0)
    assert t_default == t_zero
    assert _decode_part(t_default)["risk_level"] == 0


def test_mock_bvi_05__minted_token_validates_elsewhere():
    """MOCK-BVI-05 — a token minted by A validates on B to the full result.
    Rules: build_val_id R4."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("250.50"), "FAILED", currency="USD", risk_level=0)
    r = B.validate(tok)
    assert r == ValidationResult(
        status="FAILED", tran_id=T1, val_id=tok, amount=Decimal("250.50"), currency="USD",
        risk_level=0, risk_title="Safe", bank_tran_id="MOCKBANK-TXN-ABC-001",
        card_type="mock-visa", verify_sign=tok.rsplit(".", 1)[1], verify_key=VKEY,
    )
    assert str(r.amount) == "250.50"


def test_mock_bvi_06__deterministic():
    """MOCK-BVI-06 — same inputs give the same token on any instance; a different amount does not.
    Rules: build_val_id R5."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    t1 = mint(A, T1, Decimal("10.00"), "VALID")
    t2 = mint(A, T1, Decimal("10.00"), "VALID")
    t3 = mint(B, T1, Decimal("10.00"), "VALID")
    t4 = mint(A, T1, Decimal("10.01"), "VALID")
    assert t1 == t2 == t3
    assert t4 != t1


def test_mock_bvi_07__signature_uses_current_key(mock_settings):
    """MOCK-BVI-07 — changing SECRET_KEY changes only the signature part.
    Rules: build_val_id R2."""
    A = MockSSLCommerzClient()
    ta = mint(A, T1, Decimal("10.00"), "VALID")
    set_key(mock_settings, K2)
    tb = mint(A, T1, Decimal("10.00"), "VALID")
    ea, sa = ta.split(".")
    eb, sb = tb.split(".")
    assert ea == eb
    assert sa != sb
    assert sb == H(K2, "VALID|TXN-ABC-001|10.00|BDT|0")


# --------------------------------------------------------------------------- #
# _decode_val_id(val_id)
# --------------------------------------------------------------------------- #

def test_mock_dec_01__decodes_valid_token():
    """MOCK-DEC-01 — a valid token decodes to its payload dict.
    Rules: _decode_val_id R1."""
    A = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("10.00"), "VALID", risk_level=1)
    assert A._decode_val_id(tok) == {
        "tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 1,
    }


@pytest.mark.parametrize("make", DEC_02_INPUTS)
def test_mock_dec_02__no_dot_returns_none(make, mock_settings):
    """MOCK-DEC-02 — a value without a "." returns None without raising.
    Rules: _decode_val_id R2."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(make(A, mock_settings)) is None


@pytest.mark.parametrize("make", DEC_03_INPUTS)
def test_mock_dec_03__undecodable_returns_none(make, mock_settings):
    """MOCK-DEC-03 — undecodable base64 / non-UTF-8 / non-JSON parts return None.
    Rules: _decode_val_id R3."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(make(A, mock_settings)) is None


@pytest.mark.parametrize("make", DEC_04_INPUTS)
def test_mock_dec_04__bad_signature_returns_none(make, mock_settings):
    """MOCK-DEC-04 — a signature that does not match returns None.
    Rules: _decode_val_id R4."""
    A = MockSSLCommerzClient()
    value = make(A, mock_settings)
    assert A._decode_val_id(value) is None


@pytest.mark.xfail(strict=True, reason=BUG_581)
@pytest.mark.parametrize("value", MAL)
def test_mock_dec_05__malformed_payload_returns_none(value):
    """MOCK-DEC-05 — a JSON payload that is not a full five-field object returns None.
    Rules: _decode_val_id R5 [BUG-581]."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(value) is None


@pytest.mark.xfail(strict=True, reason=BUG_581)
def test_mock_dec_06__non_ascii_signature_returns_none():
    """MOCK-DEC-06 — a non-ASCII signature part returns None.
    Rules: _decode_val_id R6 [BUG-581]."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(NAS) is None


@pytest.mark.xfail(strict=True, reason=BUG_583)
@pytest.mark.parametrize("make", MD_OK)
def test_mock_dec_07__multi_dot_accepted_today_returns_none(make, mock_settings):
    """MOCK-DEC-07 — a multi-dot token whose last segment is the signature is rejected.
    Rules: _decode_val_id R3a [BUG-583]."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(make(A, mock_settings)) is None


@pytest.mark.parametrize("make", MD_REJ)
def test_mock_dec_08__multi_dot_rejected_returns_none(make, mock_settings):
    """MOCK-DEC-08 — multi-dot tokens whose last segment is not the signature return None.
    Rules: _decode_val_id R3a (rejected today and after the fix)."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(make(A, mock_settings)) is None


@pytest.mark.xfail(strict=True, reason=BUG_583)
@pytest.mark.parametrize("make", NCB)
def test_mock_dec_09__non_canonical_base64_returns_none(make, mock_settings):
    """MOCK-DEC-09 — a payload part that is not canonical URL-safe base64 returns None.
    Rules: _decode_val_id R3b [BUG-583]."""
    A = MockSSLCommerzClient()
    assert A._decode_val_id(make(A, mock_settings)) is None


@pytest.mark.parametrize("value", NCJ)
def test_mock_dec_10__non_canonical_json_accepted(value):
    """MOCK-DEC-10 — a correctly signed payload with non-canonical JSON layout is accepted.
    Rules: _decode_val_id R3b (JSON need not be canonical), R1."""
    A = MockSSLCommerzClient()
    d = A._decode_val_id(value)
    assert isinstance(d, dict)
    assert d["tran_id"] == T1
    assert d["amount"] == "10.00"
    assert d["currency"] == "BDT"
    assert d["status"] == "VALID"
    assert d["risk_level"] == 0


# --------------------------------------------------------------------------- #
# validate(val_id)
# --------------------------------------------------------------------------- #

def test_mock_val_01__valid_token_full_result():
    """MOCK-VAL-01 — a valid token maps to the full ValidationResult.
    Rules: validate R2, R3, R4, R5."""
    A = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("10.00"), "VALID", risk_level=0)
    r = A.validate(tok)
    assert r == ValidationResult(
        status="VALID", tran_id=T1, val_id=tok, amount=Decimal("10.00"), currency="BDT",
        risk_level=0, risk_title="Safe", bank_tran_id="MOCKBANK-TXN-ABC-001",
        card_type="mock-visa", verify_sign=S1, verify_key=VKEY,
    )
    assert type(r.amount) is Decimal
    assert str(r.amount) == "10.00"
    assert r.verify_sign == tok.rsplit(".", 1)[1]
    assert r.val_id == tok


@pytest.mark.parametrize("status", [pytest.param("FAILED", id="FAILED"), pytest.param("CANCELLED", id="CANCELLED")])
def test_mock_val_02__status_and_fields_passed_through(status):
    """MOCK-VAL-02 — status, tran_id, amount, currency come from the token.
    Rules: validate R2, R4."""
    A = MockSSLCommerzClient()
    r = A.validate(mint(A, T2, Decimal("1E+2"), status, currency="USD"))
    assert r.status == status
    assert r.tran_id == T2
    assert r.amount == Decimal("1E+2")
    assert str(r.amount) == "1E+2"
    assert r.currency == "USD"
    assert r.bank_tran_id == "MOCKBANK-TXN-XYZ-002"
    assert r.card_type == "mock-visa"


def test_mock_val_03__risk_level_one_is_risky():
    """MOCK-VAL-03 — risk_level 1 gives risk_title "Risky".
    Rules: validate R3."""
    A = MockSSLCommerzClient()
    r = A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=1))
    assert r.risk_level == 1
    assert r.risk_title == "Risky"
    assert r.status == "VALID"


def test_mock_val_04__other_risk_level_is_safe():
    """MOCK-VAL-04 — risk_level 2 gives risk_title "Safe".
    Rules: validate R3."""
    A = MockSSLCommerzClient()
    r = A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=2))
    assert r.risk_level == 2
    assert r.risk_title == "Safe"


@pytest.mark.parametrize("make", DEC_02_INPUTS + DEC_03_INPUTS + DEC_04_INPUTS + MD_REJ)
def test_mock_val_05__invalid_token_is_invalid_transaction(make, mock_settings):
    """MOCK-VAL-05 — every token _decode_val_id rejects gives INV, no exception.
    Rules: validate R1."""
    A = MockSSLCommerzClient()
    value = make(A, mock_settings)
    assert A.validate(value) == INV


@pytest.mark.xfail(strict=True, reason=BUG_581)
@pytest.mark.parametrize("value", MAL + [pytest.param(NAS, id="NAS")])
def test_mock_val_06__malformed_is_invalid_transaction(value):
    """MOCK-VAL-06 — malformed payloads and non-ASCII signatures give INV.
    Rules: validate R1a [BUG-581]."""
    A = MockSSLCommerzClient()
    assert A.validate(value) == INV


@pytest.mark.xfail(strict=True, reason=BUG_581)
def test_mock_val_07__bad_amount_is_invalid_transaction():
    """MOCK-VAL-07 — a signed non-numeric amount gives INV.
    Rules: validate R1b [BUG-581]."""
    A = MockSSLCommerzClient()
    assert A.validate(BAD_AMT) == INV


def test_mock_val_08__repeat_validation_stable():
    """MOCK-VAL-08 — validating the same token repeatedly gives the same VALID result.
    Rules: validate R6."""
    A = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("10.00"), "VALID")
    r1, r2, r3 = A.validate(tok), A.validate(tok), A.validate(tok)
    assert r1 == r2 == r3
    for r in (r1, r2, r3):
        assert r.status == "VALID"


@pytest.mark.parametrize("rl", [pytest.param(0, id="rl0"), pytest.param(1, id="rl1")])
def test_mock_val_09__result_form_verifies(rl):
    """MOCK-VAL-09 — the form built from a validation result passes verify_signature.
    Rules: validate R7; verify_signature R5."""
    A = MockSSLCommerzClient()
    r = A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=rl))
    assert A.verify_signature(FORM(r)) is True


@pytest.mark.xfail(strict=True, reason=BUG_583)
@pytest.mark.parametrize("make", MD_OK + NCB)
def test_mock_val_11__non_canonical_token_is_invalid_transaction(make, mock_settings):
    """MOCK-VAL-11 — multi-dot and non-canonical base64 tokens give INV.
    Rules: validate R1 [BUG-583] (R3a/R3b inputs)."""
    A = MockSSLCommerzClient()
    assert A.validate(make(A, mock_settings)) == INV


@pytest.mark.parametrize("value", NCJ)
def test_mock_val_12__non_canonical_json_validates(value):
    """MOCK-VAL-12 — a correctly signed non-canonical JSON payload validates to the full result.
    Rules: validate R2, R5 (non-canonical JSON)."""
    A = MockSSLCommerzClient()
    r = A.validate(value)
    assert r.status == "VALID"
    assert r.tran_id == T1
    assert r.amount == Decimal("10.00")
    assert r.currency == "BDT"
    assert r.risk_level == 0
    assert r.risk_title == "Safe"
    assert r.val_id == value
    assert r.verify_sign == S1
    assert r.verify_key == VKEY


def test_mock_val_10__validate_independent_and_side_effect_free():
    """MOCK-VAL-10 — validation does not depend on the minting instance and records nothing.
    Rules: validate R2; side effects none."""
    A = MockSSLCommerzClient()
    C = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("10.00"), "VALID")
    rc = C.validate(tok)
    q = C.query_by_tran_id(T1)
    assert rc == A.validate(tok)
    assert q == UNATT(T1)


# --------------------------------------------------------------------------- #
# query_by_tran_id(tran_id, val_id_hint=None)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="no-hint"),
        pytest.param({"val_id_hint": None}, id="hint-None"),
        pytest.param({"val_id_hint": ""}, id="hint-empty"),
    ],
)
def test_mock_qry_01__fresh_instance_unattempted(kwargs):
    """MOCK-QRY-01 — a fresh instance with no usable hint answers UNATTEMPTED.
    Rules: query_by_tran_id R1."""
    A = MockSSLCommerzClient()
    assert A.query_by_tran_id(T1, **kwargs) == UNATT(T1)


def test_mock_qry_02__record_is_per_instance():
    """MOCK-QRY-02 — minting on A does not affect lookups on B.
    Rules: query_by_tran_id R1; build_val_id R6 (per-instance)."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    mint(A, T1, Decimal("500.00"), "VALID")
    assert B.query_by_tran_id(T1) == UNATT(T1)


def test_mock_qry_03__record_for_other_tran_id_ignored():
    """MOCK-QRY-03 — a record for T2 does not answer a lookup for T1.
    Rules: query_by_tran_id R1, R1a."""
    A = MockSSLCommerzClient()
    mint(A, T2, Decimal("500.00"), "VALID")
    assert A.query_by_tran_id(T1) == UNATT(T1)


@pytest.mark.xfail(strict=True, reason=BUG_580)
@pytest.mark.parametrize("hint", [pytest.param(None, id="hint-None"), pytest.param("", id="hint-empty")])
@pytest.mark.parametrize("status", ["VALID", "FAILED", "CANCELLED"])
def test_mock_qry_04__lookup_answers_from_record(status, hint):
    """MOCK-QRY-04 — a tran_id minted on this instance is answered from the record.
    Rules: query_by_tran_id R1a [BUG-580]; build_val_id R6."""
    A = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("500.00"), status)
    r = A.query_by_tran_id(T1, val_id_hint=hint)
    assert r == A.validate(tok)
    assert r.status == status
    assert r.amount == Decimal("500.00")
    assert r.val_id == tok


@pytest.mark.xfail(strict=True, reason=BUG_580)
def test_mock_qry_05__latest_mint_wins():
    """MOCK-QRY-05 — when a tran_id is minted twice the latest outcome is answered.
    Rules: query_by_tran_id R1a [BUG-580]; build_val_id R6."""
    A = MockSSLCommerzClient()
    mint(A, T1, Decimal("500.00"), "VALID")
    tok2 = mint(A, T1, Decimal("500.00"), "CANCELLED")
    r = A.query_by_tran_id(T1)
    assert r == A.validate(tok2)
    assert r.status == "CANCELLED"
    assert r.val_id == tok2


@pytest.mark.parametrize("status", ["VALID", "FAILED", "CANCELLED"])
def test_mock_qry_06__matching_hint_is_validated(status):
    """MOCK-QRY-06 — a valid hint for the asked tran_id is answered via validate.
    Rules: query_by_tran_id R2."""
    B = MockSSLCommerzClient()
    C = MockSSLCommerzClient()
    hint = mint(B, T1, Decimal("75.25"), status)
    r = C.query_by_tran_id(T1, hint)
    assert r == C.validate(hint)
    assert r.status == status
    assert r.tran_id == T1
    assert r.amount == Decimal("75.25")


def test_mock_qry_07__hint_beats_record():
    """MOCK-QRY-07 — a valid matching hint wins over the recorded (later) outcome.
    Rules: query_by_tran_id R2."""
    A = MockSSLCommerzClient()
    tok1 = mint(A, T1, Decimal("500.00"), "FAILED")
    mint(A, T1, Decimal("500.00"), "VALID")
    r = A.query_by_tran_id(T1, tok1)
    assert r == A.validate(tok1)
    assert r.status == "FAILED"
    assert r.val_id == tok1


def test_mock_qry_08__foreign_hint_without_record():
    """MOCK-QRY-08 — a valid hint for another tran_id gives UNATTEMPTED when nothing is recorded.
    Rules: query_by_tran_id R3."""
    B = MockSSLCommerzClient()
    C = MockSSLCommerzClient()
    hint = mint(B, T2, Decimal("500.00"), "VALID")
    assert C.query_by_tran_id(T1, hint) == UNATT(T1)


@pytest.mark.xfail(strict=True, reason=BUG_580)
def test_mock_qry_09__foreign_hint_falls_back_to_record():
    """MOCK-QRY-09 — a foreign hint is ignored and the record answers.
    Rules: query_by_tran_id R3a [BUG-580]."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("500.00"), "VALID")
    hint = mint(B, T2, Decimal("20.00"), "VALID")
    r = A.query_by_tran_id(T1, hint)
    assert r == A.validate(tok)
    assert r.tran_id == T1
    assert r.status == "VALID"


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda a, mp: "abcdef", id="garbage"),
        pytest.param(lambda a, mp: TOK(P1, Z64), id="zero-signature"),
        pytest.param(_other_key, id="minted-with-K2"),
    ],
)
def test_mock_qry_10__invalid_hint_without_record(make, mock_settings):
    """MOCK-QRY-10 — an invalid hint gives UNATTEMPTED when nothing is recorded.
    Rules: query_by_tran_id R4 (no record)."""
    C = MockSSLCommerzClient()
    hint = make(MockSSLCommerzClient(), mock_settings)
    assert C.query_by_tran_id(T1, hint) == UNATT(T1)


@pytest.mark.xfail(strict=True, reason=BUG_580)
@pytest.mark.parametrize(
    "hint", [pytest.param("abcdef", id="garbage"), pytest.param(TOK(P1, Z64), id="zero-signature")]
)
def test_mock_qry_11__invalid_hint_falls_back_to_record(hint):
    """MOCK-QRY-11 — an invalid hint is ignored and the record answers.
    Rules: query_by_tran_id R4 [BUG-580] (record present)."""
    A = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("500.00"), "VALID")
    r = A.query_by_tran_id(T1, hint)
    assert r == A.validate(tok)
    assert r.status == "VALID"


@pytest.mark.xfail(strict=True, reason=BUG_580)
@pytest.mark.parametrize(
    "make",
    [pytest.param(lambda a, mp: "abcdef", id="garbage"), pytest.param(_other_key, id="minted-with-K2")],
)
def test_mock_qry_12__empty_tran_id_invalid_hint_unattempted(make, mock_settings):
    """MOCK-QRY-12 — asked "" with an invalid hint answers UNATTEMPTED, not INVALID_TRANSACTION.
    Rules: query_by_tran_id R4 [BUG-580] (asked "")."""
    C = MockSSLCommerzClient()
    hint = make(MockSSLCommerzClient(), mock_settings)
    assert C.query_by_tran_id("", hint) == UNATT("")


def test_mock_qry_13__empty_tran_id_no_hint():
    """MOCK-QRY-13 — asked "" with no hint answers UNATTEMPTED("").
    Rules: query_by_tran_id R1."""
    C = MockSSLCommerzClient()
    assert C.query_by_tran_id("") == UNATT("")


@pytest.mark.xfail(strict=True, reason=BUG_581)
@pytest.mark.parametrize(
    "hint", MAL + [pytest.param(NAS, id="NAS"), pytest.param(BAD_AMT, id="BAD_AMT")]
)
def test_mock_qry_14__malformed_hint_unattempted(hint):
    """MOCK-QRY-14 — a malformed hint is ignored (UNATTEMPTED), no exception.
    Rules: query_by_tran_id R5 [BUG-581]."""
    C = MockSSLCommerzClient()
    assert C.query_by_tran_id(T1, hint) == UNATT(T1)


def test_mock_qry_15__hint_lookup_records_nothing():
    """MOCK-QRY-15 — a hint lookup does not record anything.
    Rules: query_by_tran_id side effects none."""
    B = MockSSLCommerzClient()
    C = MockSSLCommerzClient()
    hint = mint(B, T1, Decimal("500.00"), "VALID")
    r1 = C.query_by_tran_id(T1, hint)
    r2 = C.query_by_tran_id(T1)
    assert r1 == C.validate(hint)
    assert r1.status == "VALID"
    assert r2 == UNATT(T1)


@pytest.mark.xfail(strict=True, reason=BUG_580)
def test_mock_qry_16__hint_lookup_does_not_replace_record():
    """MOCK-QRY-16 — lookups never change the record; the hint wins only for its own call.
    Rules: query_by_tran_id side effects none; R1a [BUG-580]."""
    A = MockSSLCommerzClient()
    B = MockSSLCommerzClient()
    tok = mint(A, T1, Decimal("500.00"), "VALID")
    other = mint(B, T1, Decimal("500.00"), "FAILED")
    r0 = A.query_by_tran_id(T2)
    r1 = A.query_by_tran_id(T1, other)
    r2 = A.query_by_tran_id(T1)
    assert r0 == UNATT(T2)
    assert r1 == A.validate(other)
    assert r1.status == "FAILED"
    assert r2 == A.validate(tok)
    assert r2.status == "VALID"


@pytest.mark.xfail(strict=True, reason=BUG_583)
@pytest.mark.parametrize("make", MD_OK + NCB_P1)
def test_mock_qry_17__non_canonical_hint_unattempted(make, mock_settings):
    """MOCK-QRY-17 — a non-canonical hint is rejected and ignored (UNATTEMPTED).
    Rules: query_by_tran_id R4 via validate R1 [BUG-583] (no record)."""
    C = MockSSLCommerzClient()
    hint = make(MockSSLCommerzClient(), mock_settings)
    assert C.query_by_tran_id(T1, hint) == UNATT(T1)


# --------------------------------------------------------------------------- #
# verify_signature(payload)
# --------------------------------------------------------------------------- #

def test_mock_vsig_01__valid_form_true():
    """MOCK-VSIG-01 — a correctly signed form verifies.
    Rules: verify_signature R3."""
    A = MockSSLCommerzClient()
    assert A.verify_signature(F1) is True


def test_mock_vsig_02__int_risk_level_true():
    """MOCK-VSIG-02 — an int risk_level signs like its string form.
    Rules: verify_signature R3."""
    A = MockSSLCommerzClient()
    assert A.verify_signature({**F1, "risk_level": 0}) is True


@pytest.mark.parametrize(
    ("field", "new"),
    [
        pytest.param("status", "FAILED", id="status"),
        pytest.param("tran_id", T2, id="tran_id"),
        pytest.param("amount", "10.0", id="amount"),
        pytest.param("currency", "USD", id="currency"),
        pytest.param("risk_level", "1", id="risk_level"),
    ],
)
def test_mock_vsig_03__changed_signed_field_false(field, new):
    """MOCK-VSIG-03 — changing any signed field fails verification.
    Rules: verify_signature R3."""
    A = MockSSLCommerzClient()
    assert A.verify_signature({**F1, field: new}) is False


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**F1, "val_id": "VAL-OTHER"}, id="val_id-changed"),
        pytest.param(_without(F1, "val_id"), id="val_id-removed"),
        pytest.param({**F1, "verify_key": "x"}, id="verify_key-changed"),
        pytest.param({**F1, "bank_tran_id": "B-1"}, id="extra-key"),
    ],
)
def test_mock_vsig_04__unsigned_fields_ignored(payload):
    """MOCK-VSIG-04 — fields outside the signed five do not affect verification.
    Rules: verify_signature R3 (unsigned fields)."""
    A = MockSSLCommerzClient()
    assert A.verify_signature(payload) is True


@pytest.mark.parametrize(
    "sig",
    [
        pytest.param(S1.upper(), id="uppercase"),
        pytest.param(Z64, id="zeros"),
        pytest.param(H(K2, "VALID|TXN-ABC-001|10.00|BDT|0"), id="K2"),
        pytest.param(S1[:-1], id="truncated"),
    ],
)
def test_mock_vsig_05__wrong_signature_false(sig):
    """MOCK-VSIG-05 — a signature that does not match exactly fails.
    Rules: verify_signature R3."""
    A = MockSSLCommerzClient()
    assert A.verify_signature({**F1, "verify_sign": sig}) is False


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_without(F1, "verify_sign"), id="removed"),
        pytest.param({**F1, "verify_sign": None}, id="None"),
        pytest.param({**F1, "verify_sign": ""}, id="empty"),
    ],
)
def test_mock_vsig_06__missing_signature_false(payload):
    """MOCK-VSIG-06 — a missing or empty verify_sign fails.
    Rules: verify_signature R1."""
    A = MockSSLCommerzClient()
    assert A.verify_signature(payload) is False


@pytest.mark.parametrize(
    "payload",
    [pytest.param(_without(F1, f), id=f"{f}-removed") for f in SIGNED]
    + [pytest.param({**F1, f: None}, id=f"{f}-None") for f in SIGNED],
)
def test_mock_vsig_07__missing_signed_field_false(payload):
    """MOCK-VSIG-07 — a missing or None signed field fails without raising.
    Rules: verify_signature R2."""
    A = MockSSLCommerzClient()
    assert A.verify_signature(payload) is False


def test_mock_vsig_08__empty_string_field_is_present():
    """MOCK-VSIG-08 — an empty-string field counts as present and is signed as "".
    Rules: verify_signature R2 (empty string present)."""
    A = MockSSLCommerzClient()
    assert A.verify_signature(
        {**F1, "currency": "", "verify_sign": H(K1, "VALID|TXN-ABC-001|10.00||0")}
    ) is True


@pytest.mark.xfail(strict=True, reason=BUG_582)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("é", id="e-acute"),
        pytest.param("é" + S1[1:], id="non-ascii-prefix"),
        pytest.param(123, id="int"),
        pytest.param(["x"], id="list"),
    ],
)
def test_mock_vsig_09__non_ascii_or_non_string_false(value):
    """MOCK-VSIG-09 — a non-ASCII or non-string verify_sign returns False, never raises.
    Rules: verify_signature R4 [BUG-582]."""
    A = MockSSLCommerzClient()
    assert A.verify_signature({**F1, "verify_sign": value}) is False
