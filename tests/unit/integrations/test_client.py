"""Unit tests for app/integrations/sslcommerz/client.py.

Implements tests/unit/integrations/client.cases.md (revision 2), one test per
case. Pure Python module: no database, no mocks, no time patching. The
dataclasses are constructed directly; the ABC is exercised with throwaway
subclasses defined in this file.
"""
from decimal import Decimal

import pytest

from app.integrations.sslcommerz.client import (
    InitSessionRequest,
    InitSessionResult,
    SSLCommerzClient,
    ValidationResult,
)

# --------------------------------------------------------------------------- #
# Conventions -> constants / helper classes
# --------------------------------------------------------------------------- #

BUG_020 = "BUG-020: value_a..value_d never sent to the gateway (InitSessionRequest lacks the fields)"

# Convention "REQ_KW": the ten required fields by keyword (all distinct values)
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
REQ_ORDER = (
    "tran_id", "amount", "currency", "success_url", "fail_url",
    "cancel_url", "ipn_url", "cus_name", "cus_email", "cus_phone",
)

ABSTRACT_METHODS = ("init_session", "validate", "query_by_tran_id", "verify_signature")


# Convention "FullClient" / "Missing<X>": method bodies shared by both
def _init_session(self, req):
    return InitSessionResult(
        status="SUCCESS", session_key="SK-1",
        gateway_page_url="https://gw.example/pay/SK-1",
    )


def _validate(self, val_id):
    return ValidationResult(status="VALID", tran_id="TXN-0001", val_id=val_id)


def _query_by_tran_id(self, tran_id, val_id_hint=None):
    return ValidationResult(status="VALIDATED", tran_id=tran_id, val_id=val_id_hint)


def _verify_signature(self, payload):
    return True


_BODIES = {
    "init_session": _init_session,
    "validate": _validate,
    "query_by_tran_id": _query_by_tran_id,
    "verify_signature": _verify_signature,
}


# Convention "FullClient": overrides all four methods
class FullClient(SSLCommerzClient):
    init_session = _init_session
    validate = _validate
    query_by_tran_id = _query_by_tran_id
    verify_signature = _verify_signature


# Convention "Missing<X>": overrides the three methods other than X
def missing(method_name):
    attrs = {k: v for k, v in _BODIES.items() if k != method_name}
    return type(f"Missing_{method_name}", (SSLCommerzClient,), attrs)


# Convention "SuperClient": every override delegates to super()
class SuperClient(SSLCommerzClient):
    def init_session(self, req):
        return super().init_session(req)

    def validate(self, val_id):
        return super().validate(val_id)

    def query_by_tran_id(self, tran_id, val_id_hint=None):
        return super().query_by_tran_id(tran_id)

    def verify_signature(self, payload):
        return super().verify_signature(payload)


# SSLC-QRY-03 variant: SuperClient whose override passes val_id_hint through
class SuperClientWithHint(SuperClient):
    def query_by_tran_id(self, tran_id, val_id_hint=None):
        return super(SuperClient, self).query_by_tran_id(tran_id, val_id_hint=val_id_hint)


# --------------------------------------------------------------------------- #
# InitSessionRequest
# --------------------------------------------------------------------------- #

def test_sslc_req_01__keyword_construction_keeps_values_and_defaults():
    """SSLC-REQ-01 — keyword construction keeps every value; defaults applied.
    Rules: InitSessionRequest R1, R2."""
    r = InitSessionRequest(**REQ_KW)
    assert isinstance(r, InitSessionRequest)
    for name, value in REQ_KW.items():
        assert getattr(r, name) == value, name
    assert r.amount == Decimal("10.005")
    assert type(r.amount) is Decimal
    assert str(r.amount) == "10.005"
    assert r.product_name == "Workspace Subscription"
    assert r.product_category == "subscription"


def test_sslc_req_02__positional_construction_in_declared_order():
    """SSLC-REQ-02 — positional construction maps values in declared order.
    Rules: InitSessionRequest R1."""
    r = InitSessionRequest(*(REQ_KW[n] for n in REQ_ORDER))
    for name in REQ_ORDER:
        assert getattr(r, name) == REQ_KW[name], name
    assert r.success_url == "https://app.example/pay/success"
    assert r.cus_phone == "01700000000"
    assert r.product_name == "Workspace Subscription"
    assert r.product_category == "subscription"


def test_sslc_req_03__no_conversion_trimming_or_validation():
    """SSLC-REQ-03 — values stored as passed: str amount, untrimmed id, bad email, empty currency.
    Rules: InitSessionRequest R1."""
    r = InitSessionRequest(**{
        **REQ_KW, "amount": "10.00", "tran_id": "  TXN-0001  ",
        "cus_email": "NOT-AN-EMAIL", "currency": "",
    })
    assert r.amount == "10.00"
    assert type(r.amount) is str
    assert r.tran_id == "  TXN-0001  "
    assert r.cus_email == "NOT-AN-EMAIL"
    assert r.currency == ""


def test_sslc_req_04__product_fields_given_are_kept():
    """SSLC-REQ-04 — given product_name / product_category are kept.
    Rules: InitSessionRequest R2."""
    r = InitSessionRequest(**REQ_KW, product_name="Pro Plan (12 months)", product_category="plan")
    assert r.product_name == "Pro Plan (12 months)"
    assert r.product_category == "plan"


def test_sslc_req_05__one_product_field_given_other_defaults():
    """SSLC-REQ-05 — only product_name given; product_category keeps its default.
    Rules: InitSessionRequest R2."""
    r = InitSessionRequest(**REQ_KW, product_name="Pro Plan")
    assert r.product_name == "Pro Plan"
    assert r.product_category == "subscription"


@pytest.mark.parametrize("omitted", [pytest.param(n, id=f"SSLC-REQ-06-{n}") for n in REQ_ORDER])
def test_sslc_req_06__missing_required_field_raises(omitted):
    """SSLC-REQ-06 — omitting any one of the ten required fields raises TypeError.
    Rules: InitSessionRequest R3; Errors row 1."""
    kw = {k: v for k, v in REQ_KW.items() if k != omitted}
    with pytest.raises(TypeError):
        InitSessionRequest(**kw)


def test_sslc_req_07__unknown_keyword_raises():
    """SSLC-REQ-07 — an undeclared keyword raises TypeError.
    Rules: InitSessionRequest R3; Errors row 1."""
    with pytest.raises(TypeError):
        InitSessionRequest(**REQ_KW, foo="x")


def test_sslc_req_08__required_fields_alone_construct():
    """SSLC-REQ-08 — the ten required fields alone construct (value_* optional; regression guard).
    Rules: InitSessionRequest R3a."""
    r = InitSessionRequest(**REQ_KW)
    assert isinstance(r, InitSessionRequest)
    assert r.tran_id == "TXN-0001"


@pytest.mark.xfail(strict=True, reason=BUG_020)
def test_sslc_req_09__value_fields_kept():
    """SSLC-REQ-09 — value_a..value_d are accepted and kept as passed.
    Rules: InitSessionRequest R1a [BUG-020]."""
    r = InitSessionRequest(
        **REQ_KW, value_a="plan:pro;months:12", value_b="ws:42",
        value_c="coupon:NONE", value_d="src:web",
    )
    assert r.value_a == "plan:pro;months:12"
    assert r.value_b == "ws:42"
    assert r.value_c == "coupon:NONE"
    assert r.value_d == "src:web"
    assert r.tran_id == "TXN-0001"


@pytest.mark.xfail(strict=True, reason=BUG_020)
def test_sslc_req_10__value_fields_default_none():
    """SSLC-REQ-10 — value_a..value_d default to None.
    Rules: InitSessionRequest R1a [BUG-020]."""
    r = InitSessionRequest(**REQ_KW)
    assert r.value_a is None
    assert r.value_b is None
    assert r.value_c is None
    assert r.value_d is None


@pytest.mark.xfail(strict=True, reason=BUG_020)
def test_sslc_req_11__one_value_field_given_others_none():
    """SSLC-REQ-11 — only value_c given; the other three default to None.
    Rules: InitSessionRequest R1a [BUG-020]."""
    r = InitSessionRequest(**REQ_KW, value_c="only-c")
    assert r.value_c == "only-c"
    assert r.value_a is None
    assert r.value_b is None
    assert r.value_d is None


def test_sslc_req_12__equality_by_field_values():
    """SSLC-REQ-12 — equal field values compare equal; a different amount does not.
    Rules: InitSessionRequest R4."""
    a = InitSessionRequest(**REQ_KW)
    b = InitSessionRequest(**REQ_KW)
    c = InitSessionRequest(**{**REQ_KW, "amount": Decimal("10.006")})
    assert (a == b) is True
    assert a is not b
    assert (a == c) is False


def test_sslc_req_13__instances_are_mutable():
    """SSLC-REQ-13 — fields can be reassigned after construction.
    Rules: InitSessionRequest R4."""
    r = InitSessionRequest(**REQ_KW)
    r.amount = Decimal("99.99")
    r.product_name = "Changed"
    assert r.amount == Decimal("99.99")
    assert r.product_name == "Changed"


# --------------------------------------------------------------------------- #
# InitSessionResult
# --------------------------------------------------------------------------- #

def test_sslc_res_01__status_only_optionals_none():
    """SSLC-RES-01 — with only status, the three optional fields are None.
    Rules: InitSessionResult R1."""
    r = InitSessionResult(status="SUCCESS")
    assert isinstance(r, InitSessionResult)
    assert r.status == "SUCCESS"
    assert r.session_key is None
    assert r.gateway_page_url is None
    assert r.failed_reason is None


def test_sslc_res_02__all_fields_kept():
    """SSLC-RES-02 — all given values kept as passed.
    Rules: InitSessionResult R2."""
    r = InitSessionResult(
        status="FAILED", session_key="SK-9",
        gateway_page_url="https://gw.example/pay/SK-9", failed_reason="Store is de-active",
    )
    assert r.status == "FAILED"
    assert r.session_key == "SK-9"
    assert r.gateway_page_url == "https://gw.example/pay/SK-9"
    assert r.failed_reason == "Store is de-active"


@pytest.mark.parametrize("status", [
    pytest.param("success", id="SSLC-RES-03-lowercase"),
    pytest.param("", id="SSLC-RES-03-empty"),
])
def test_sslc_res_03__any_status_string_accepted(status):
    """SSLC-RES-03 — any status string accepted (no enum check).
    Rules: InitSessionResult R2."""
    r = InitSessionResult(status=status)
    assert r.status == status


def test_sslc_res_04__missing_status_raises():
    """SSLC-RES-04 — omitting status raises TypeError.
    Rules: InitSessionResult R3; Errors row 1."""
    with pytest.raises(TypeError):
        InitSessionResult(session_key="SK-1")


def test_sslc_res_05__unknown_keyword_raises():
    """SSLC-RES-05 — an undeclared keyword raises TypeError.
    Rules: InitSessionResult R3; Errors row 1."""
    with pytest.raises(TypeError):
        InitSessionResult(status="SUCCESS", foo="x")


def test_sslc_res_06__equality_by_field_values():
    """SSLC-RES-06 — equal field values compare equal; different session_key does not.
    Rules: InitSessionResult R4."""
    a = InitSessionResult(status="SUCCESS", session_key="SK-1")
    b = InitSessionResult(status="SUCCESS", session_key="SK-1")
    c = InitSessionResult(status="SUCCESS", session_key="SK-2")
    assert (a == b) is True
    assert (a == c) is False


# --------------------------------------------------------------------------- #
# ValidationResult
# --------------------------------------------------------------------------- #

VAL_OPTIONAL = (
    "val_id", "amount", "currency", "risk_level", "risk_title",
    "bank_tran_id", "card_type", "verify_sign", "verify_key",
)


def test_sslc_val_01__status_and_tran_id_only_optionals_none():
    """SSLC-VAL-01 — with only status and tran_id, the nine optional fields are None.
    Rules: ValidationResult R1."""
    r = ValidationResult(status="VALID", tran_id="TXN-0001")
    assert isinstance(r, ValidationResult)
    assert r.status == "VALID"
    assert r.tran_id == "TXN-0001"
    for name in VAL_OPTIONAL:
        assert getattr(r, name) is None, name


def test_sslc_val_02__all_fields_kept():
    """SSLC-VAL-02 — all eleven given values kept exactly as passed.
    Rules: ValidationResult R2."""
    kw = {
        "status": "VALIDATED", "tran_id": "TXN-0002", "val_id": "VAL-77",
        "amount": Decimal("100.00"), "currency": "BDT", "risk_level": 5,
        "risk_title": "Unusual", "bank_tran_id": "BANK-1",
        "card_type": "VISA-Dutch Bangla", "verify_sign": "sig-abc",
        "verify_key": "amount,currency,tran_id",
    }
    r = ValidationResult(**kw)
    for name, value in kw.items():
        assert getattr(r, name) == value, name
    assert type(r.amount) is Decimal
    assert str(r.amount) == "100.00"
    assert r.risk_level == 5


def test_sslc_val_03__any_status_string_accepted():
    """SSLC-VAL-03 — a non-conventional status string is accepted.
    Rules: ValidationResult R2."""
    r = ValidationResult(status="NOT_A_STATUS", tran_id="TXN-0003")
    assert r.status == "NOT_A_STATUS"


def test_sslc_val_04__missing_status_raises():
    """SSLC-VAL-04 — omitting status raises TypeError.
    Rules: ValidationResult R3; Errors row 1."""
    with pytest.raises(TypeError):
        ValidationResult(tran_id="TXN-0001")


def test_sslc_val_05__missing_tran_id_raises():
    """SSLC-VAL-05 — omitting tran_id raises TypeError.
    Rules: ValidationResult R3; Errors row 1."""
    with pytest.raises(TypeError):
        ValidationResult(status="VALID")


def test_sslc_val_06__unknown_keyword_raises():
    """SSLC-VAL-06 — an undeclared keyword raises TypeError.
    Rules: ValidationResult R3; Errors row 1."""
    with pytest.raises(TypeError):
        ValidationResult(status="VALID", tran_id="TXN-0001", foo="x")


def test_sslc_val_07__equality_by_field_values():
    """SSLC-VAL-07 — equal field values compare equal; different amount does not.
    Rules: ValidationResult R4."""
    a = ValidationResult(status="VALID", tran_id="TXN-0001", amount=Decimal("5.00"))
    b = ValidationResult(status="VALID", tran_id="TXN-0001", amount=Decimal("5.00"))
    c = ValidationResult(status="VALID", tran_id="TXN-0001", amount=Decimal("6.00"))
    assert (a == b) is True
    assert (a == c) is False


# --------------------------------------------------------------------------- #
# SSLCommerzClient.init_session
# --------------------------------------------------------------------------- #

def test_sslc_init_01__base_class_not_instantiable():
    """SSLC-INIT-01 — SSLCommerzClient() raises TypeError naming all four abstract methods.
    Rules: init_session R1; Errors row 1."""
    with pytest.raises(TypeError) as exc:
        SSLCommerzClient()
    msg = str(exc.value)
    for name in ABSTRACT_METHODS:
        assert name in msg, name


def test_sslc_init_02__missing_init_session_not_instantiable():
    """SSLC-INIT-02 — a subclass without init_session cannot be instantiated.
    Rules: init_session R2; Errors row 1."""
    cls = missing("init_session")
    with pytest.raises(TypeError):
        cls()


def test_sslc_init_03__full_subclass_instantiable_and_own_methods_run():
    """SSLC-INIT-03 — a subclass overriding all four instantiates; its own methods run.
    Rules: init_session R2."""
    req = InitSessionRequest(**REQ_KW)
    client = FullClient()
    assert isinstance(client, SSLCommerzClient)
    assert client.init_session(req) == InitSessionResult(
        status="SUCCESS", session_key="SK-1", gateway_page_url="https://gw.example/pay/SK-1",
    )
    assert client.validate("VAL-1") == ValidationResult(
        status="VALID", tran_id="TXN-0001", val_id="VAL-1",
    )
    assert client.query_by_tran_id("TXN-5", val_id_hint="VAL-5") == ValidationResult(
        status="VALIDATED", tran_id="TXN-5", val_id="VAL-5",
    )
    assert client.verify_signature({"verify_sign": "x"}) is True


def test_sslc_init_04__base_init_session_raises_not_implemented():
    """SSLC-INIT-04 — super().init_session(req) raises NotImplementedError with no message.
    Rules: init_session R3; Errors row 2."""
    req = InitSessionRequest(**REQ_KW)
    with pytest.raises(NotImplementedError) as exc:
        SuperClient().init_session(req)
    assert exc.value.args == ()


# --------------------------------------------------------------------------- #
# SSLCommerzClient.validate
# --------------------------------------------------------------------------- #

def test_sslc_vald_01__missing_validate_not_instantiable():
    """SSLC-VALD-01 — a subclass without validate cannot be instantiated.
    Rules: validate R1; Errors row 1."""
    cls = missing("validate")
    with pytest.raises(TypeError):
        cls()


def test_sslc_vald_02__base_validate_raises_not_implemented():
    """SSLC-VALD-02 — super().validate(val_id) raises NotImplementedError with no message.
    Rules: validate R2; Errors row 2."""
    with pytest.raises(NotImplementedError) as exc:
        SuperClient().validate("VAL-1")
    assert exc.value.args == ()


# --------------------------------------------------------------------------- #
# SSLCommerzClient.query_by_tran_id
# --------------------------------------------------------------------------- #

def test_sslc_qry_01__missing_query_by_tran_id_not_instantiable():
    """SSLC-QRY-01 — a subclass without query_by_tran_id cannot be instantiated.
    Rules: query_by_tran_id R1; Errors row 1."""
    cls = missing("query_by_tran_id")
    with pytest.raises(TypeError):
        cls()


def test_sslc_qry_02__base_query_raises_not_implemented():
    """SSLC-QRY-02 — super().query_by_tran_id(tran_id) raises NotImplementedError with no message.
    Rules: query_by_tran_id R2; Errors row 2."""
    with pytest.raises(NotImplementedError) as exc:
        SuperClient().query_by_tran_id("TXN-5")
    assert exc.value.args == ()


def test_sslc_qry_03__base_query_accepts_val_id_hint_keyword():
    """SSLC-QRY-03 — base accepts val_id_hint as a keyword; raises NotImplementedError, not TypeError.
    Rules: query_by_tran_id R2; Errors row 2."""
    with pytest.raises(NotImplementedError) as exc:
        SuperClientWithHint().query_by_tran_id("TXN-5", val_id_hint="VAL-5")
    assert exc.value.args == ()


# --------------------------------------------------------------------------- #
# SSLCommerzClient.verify_signature
# --------------------------------------------------------------------------- #

def test_sslc_sig_01__missing_verify_signature_not_instantiable():
    """SSLC-SIG-01 — a subclass without verify_signature cannot be instantiated.
    Rules: verify_signature R1; Errors row 1."""
    cls = missing("verify_signature")
    with pytest.raises(TypeError):
        cls()


def test_sslc_sig_02__base_verify_signature_raises_not_implemented():
    """SSLC-SIG-02 — super().verify_signature(payload) raises NotImplementedError with no message.
    Rules: verify_signature R2; Errors row 2."""
    with pytest.raises(NotImplementedError) as exc:
        SuperClient().verify_signature({"verify_sign": "abc", "verify_key": "tran_id"})
    assert exc.value.args == ()
