"""Unit tests for app/managers/payment_transaction_manager.py.

Implements tests/unit/managers/payment_transaction_manager.cases.md (revision 5),
one test per case. Real Postgres session (`db` fixture). Mocked externals, per the
spec's Overview: `get_sslcommerz_client`, `utcnow` (both patched in the manager
module) and, only where a case asks for it, `secrets.token_hex`.
"""
# ruff: noqa: SIM117, FURB157, C408  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`; Decimal strings and dict(...) keep the cards' literals)
import dataclasses
import re
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import DataError, IntegrityError

from app.core.config import settings
from app.integrations.sslcommerz.client import (
    InitSessionResult,
    SSLCommerzClient,
    ValidationResult,
)
from app.managers.payment_transaction_manager import payment_transaction_manager as mgr
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_transaction_event import PaymentTransactionEvent
from app.models.workspace_member import WorkspaceMember
from app.schemas.payment_transaction import InitiatePaymentRequest
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants / fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Time": NOW (patched utcnow), V0 (earlier validated_at), T's updated_at
NOW = datetime(2026, 9, 27, 12, 0, 0)  # noqa: DTZ001
V0 = datetime(2026, 9, 27, 11, 0, 0)  # noqa: DTZ001
UPD0 = datetime(2026, 1, 1, 0, 0)  # noqa: DTZ001

# Convention "A26 = 'a'*26, B26 = 'b'*26, ..."
A26 = "a" * 26
B26 = "b" * 26
C26 = "c" * 26
D26 = "d" * 26

# Convention "Gateway fields"
GATEWAY_FIELDS = ("val_id", "risk_level", "risk_title", "bank_tran_id", "card_type", "verify_sign")
OK_FIELDS = ("VAL-1", 0, "Safe", "BANK-1", "VISA-Brac bank", "SIG-1")
NONE_FIELDS = (None,) * 6

PATCH_UTCNOW = "app.managers.payment_transaction_manager.utcnow"
PATCH_CLIENT = "app.managers.payment_transaction_manager.get_sslcommerz_client"
PATCH_TOKEN_HEX = "app.managers.payment_transaction_manager.secrets.token_hex"

HIGH_RISK_DESC = "Validated via ipn callback but flagged high-risk (Suspicious card) — held for review"

# Convention "Gateway": OK = the default passing validate() answer
OK = ValidationResult(
    status="VALID", tran_id=A26, val_id="VAL-1", amount=Decimal("500.00"), currency="BDT",
    risk_level=0, risk_title="Safe", bank_tran_id="BANK-1", card_type="VISA-Brac bank",
    verify_sign="SIG-1",
)


def ok(**overrides):
    """Convention "OK with X": OK with field X overridden."""
    return dataclasses.replace(OK, **overrides)


def invalid(tran_id=""):
    return ValidationResult(status="INVALID_TRANSACTION", tran_id=tran_id)


def unattempted(tran_id, *args, **kwargs):
    """Convention "Gateway": default query_by_tran_id side effect."""
    return ValidationResult(status="UNATTEMPTED", tran_id=tran_id)


def query_map(mapping):
    """query_by_tran_id side effect: per tran_id a result, or an exception to raise;
    tran_ids not in the mapping get the UNATTEMPTED default."""
    def side_effect(tran_id, *args, **kwargs):
        value = mapping.get(tran_id)
        if value is None:
            return unattempted(tran_id)
        if isinstance(value, BaseException):
            raise value
        return value
    return side_effect


# Convention "Time": utcnow patched to return NOW in every test
@pytest.fixture(autouse=True)
def clock():
    with patch(PATCH_UTCNOW, return_value=NOW) as m:
        yield m


# Convention "Gateway": get_sslcommerz_client patched in every test
@pytest.fixture(autouse=True)
def gw():
    client = MagicMock(spec=SSLCommerzClient)
    client.init_session.return_value = InitSessionResult(
        status="SUCCESS", session_key="SESS-1",
        gateway_page_url="https://sandbox.example/pay/SESS-1", failed_reason=None,
    )
    client.validate.return_value = OK
    client.query_by_tran_id.side_effect = unattempted
    with patch(PATCH_CLIENT, return_value=client):
        yield client


def assert_no_gateway_calls(gw):
    assert gw.method_calls == []


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


def _member(db, ws, profile):
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=profile.id, role="owner", status="active"))
    db.flush()


# Convention "U1 = a profile in W1 named Rahim Uddin / rahim@example.com"
@pytest.fixture
def u1(db, w1):
    p = make_profile(db, name="Rahim Uddin", email="rahim@example.com")
    _member(db, w1, p)
    return p


# Convention "U2 = a profile in W2"
@pytest.fixture
def u2(db, w2):
    p = make_profile(db)
    _member(db, w2, p)
    return p


# Convention "T": the standard payment_transactions row (no failed_reason /
# outcome_verified unless a case passes them -> TypeError today, BUG-026/019).
def mk_txn(db, ws, user, *, tran_id=A26, **overrides):
    fields = dict(
        workspace_id=ws.id, tran_id=tran_id, status="INITIATED", amount=Decimal("500.00"),
        currency="BDT", cus_phone="01711000000", initiated_by=user.id,
        initiated_at=NOW - timedelta(hours=2), updated_at=UPD0,
    )
    fields.update(overrides)
    row = PaymentTransaction(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "Re-read": expire the session objects, then query again
def reread(db, row_id):
    db.expire_all()
    return db.get(PaymentTransaction, row_id)


def events(db, txn_id):
    db.expire_all()
    return db.scalars(
        select(PaymentTransactionEvent)
        .where(PaymentTransactionEvent.payment_transaction_id == txn_id)
        .order_by(PaymentTransactionEvent.id)
    ).all()


def ev_types(evs):
    return [e.event_type for e in evs]


def ev_tuples(evs):
    return [
        (e.event_type, e.description, e.payment_transaction_id, e.workspace_id, e.performed_by, e.metadata_json)
        for e in evs
    ]


# Convention "Events": E(type, "desc") with the txn's id and workspace
def E(txn_id, ws_id, event_type, description, performed_by=None, metadata=None):
    return (event_type, description, txn_id, ws_id, performed_by, metadata)


def n_txns(db, ws_id=None):
    db.expire_all()
    q = select(func.count()).select_from(PaymentTransaction)
    if ws_id is not None:
        q = q.where(PaymentTransaction.workspace_id == ws_id)
    return db.scalar(q)


def n_events(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(PaymentTransactionEvent))


def txns_in(db, ws_id):
    db.expire_all()
    return db.scalars(
        select(PaymentTransaction).where(PaymentTransaction.workspace_id == ws_id).order_by(PaymentTransaction.id)
    ).all()


def gw_fields(row):
    return tuple(getattr(row, f) for f in GATEWAY_FIELDS)


# Convention "SQL capture": before_cursor_execute listener on the test engine
class SqlCapture:
    def __init__(self, engine):
        self.engine = engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    def has_select_for_update_on_txns(self):
        return any(
            s.lstrip().upper().startswith("SELECT") and "payment_transactions" in s and "FOR UPDATE" in s
            for s in self.statements
        )


# initiate_payment default request REQ
def REQ(**overrides):
    fields = dict(amount=Decimal("500"), currency="BDT", cus_phone="01711000000")
    fields.update(overrides)
    return InitiatePaymentRequest(**fields)


def initiate(db, w1, u1, request=None, **kw):
    return mgr.initiate_payment(db, workspace_id=w1.id, user=u1, request=request or REQ(**kw))


def assert_returns_reread(db, res, ws_id, status):
    """initiate_payment return check (cases rev 4): the returned txn's `id` equals
    the re-read txn's `id` (the only txn in the workspace), with `status`."""
    assert ids(txns_in(db, ws_id)) == [res.id]
    assert res.status == status


def gw_request(gw):
    return gw.init_session.call_args.args[0]


def apply_(db, txn, result, source="ipn callback"):
    return mgr._apply_validation_result(db, txn, result, source)


def fin(db, *, tran_id=A26, val_id="VAL-1", source="ipn"):
    return mgr.finalize_from_gateway(db, tran_id=tran_id, val_id=val_id, source=source)


def mtw(db, terminal_status, source, *, tran_id=A26):
    return mgr.mark_terminal_without_validation(db, tran_id=tran_id, terminal_status=terminal_status, source=source)


def rr(db, txn_id, ws_id, user_id, approve, note):
    return mgr.resolve_risk(db, transaction_id=txn_id, workspace_id=ws_id, user_id=user_id, approve=approve, note=note)


def rec(db, **kw):
    return mgr.reconcile_stuck_transactions(db, **kw)


def ids(rows):
    return [r.id for r in rows]


# Convention "A RISK_HOLD row is reached via _apply_validation_result(OK with
# risk_level=1, risk_title='Suspicious card', 'ipn callback')"
def to_risk_hold(db, txn):
    return apply_(db, txn, ok(risk_level=1, risk_title="Suspicious card"))


# resolve_risk "H": T brought to RISK_HOLD with utcnow returning V0, then NOW
def make_h(db, ws, user, clock):
    t = mk_txn(db, ws, user)
    clock.return_value = V0
    to_risk_hold(db, t)
    clock.return_value = NOW
    return t


# resolve_risk "H*": direct insert with H's values plus outcome_verified=True
def make_h_star(db, ws, user):
    return mk_txn(
        db, ws, user, status="RISK_HOLD", val_id="VAL-1", risk_level=1, risk_title="Suspicious card",
        bank_tran_id="BANK-1", card_type="VISA-Brac bank", verify_sign="SIG-1", validated_at=V0,
        outcome_verified=True,
    )


def xbug(*bugs):
    return pytest.mark.xfail(strict=True, reason="; ".join(bugs))


BUG019 = "BUG-019: Refused checkout start leaves no record and returns 502"
BUG020 = "BUG-020: value_a..value_d never sent to the gateway"
BUG021 = "BUG-021: Amounts with > 2 decimals or >= 10^13 accepted"
BUG022 = "BUG-022: Currency code not validated or normalised"
BUG023 = "BUG-023: Unknown or foreign val_id permanently fails the transaction"
BUG024 = "BUG-024: Missing amount/currency in gateway answer counts as a match"
BUG025 = "BUG-025: Cancelled payment status depends on which channel arrives first"
BUG026 = "BUG-026: Unverified redirect outcome blocks later verified result"
BUG027 = "BUG-027: Verified result after EXPIRED is ignored"
BUG028 = "BUG-028: Event type names differ from the documented list"
BUG029 = "BUG-029: Risk-hold resolution does not lock the row"
BUG030 = "BUG-030: Sweep labels gateway failures/cancellations as EXPIRED"
BUG031 = "BUG-031: Sweep can never recover a paid transaction with the mock gateway"
BUG032 = "BUG-032: One gateway error aborts the whole sweep"


# =========================================================================== #
# _log_event
# =========================================================================== #

def test_ptm_log_01__event_row_with_all_fields(db, w2, u2):
    """PTM-LOG-01 — _log_event inserts one event with every field set.
    Rules: _log_event R1."""
    t = mk_txn(db, w2, u2)
    tid = t.id
    ret = mgr._log_event(
        db, t, "initiated", "Checkout session created for 500 BDT",
        performed_by=u2.id, metadata={"session_key": "SESS-1"},
    )
    assert ret is None
    evs = events(db, tid)
    assert len(evs) == 1
    e = evs[0]
    assert e.id is not None
    assert e.workspace_id == w2.id
    assert e.payment_transaction_id == tid
    assert e.event_type == "initiated"
    assert e.description == "Checkout session created for 500 BDT"
    assert e.performed_by == u2.id
    assert e.metadata_json == {"session_key": "SESS-1"}
    assert e.created_at is not None


def test_ptm_log_02__defaults_none(db, w1, u1):
    """PTM-LOG-02 — without performed_by/metadata both are stored as None.
    Rules: _log_event R1."""
    t = mk_txn(db, w1, u1)
    tid = t.id
    ret = mgr._log_event(db, t, "expired", "x")
    assert ret is None
    evs = events(db, tid)
    assert len(evs) == 1
    e = evs[0]
    assert e.event_type == "expired"
    assert e.description == "x"
    assert e.performed_by is None
    assert e.metadata_json is None
    assert e.workspace_id == w1.id


def test_ptm_log_03__event_type_50_chars(db, w1, u1):
    """PTM-LOG-03 — a 50-char event_type is stored.
    Rules: _log_event R2."""
    t = mk_txn(db, w1, u1)
    tid = t.id
    ret = mgr._log_event(db, t, "e" * 50, "fifty")
    assert ret is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "e" * 50


def test_ptm_log_04__event_type_51_chars_data_error(db, w1, u1):
    """PTM-LOG-04 — a 51-char event_type raises DataError and writes nothing.
    Rules: _log_event R2; Errors row 1."""
    t = mk_txn(db, w1, u1)
    tid = t.id
    with pytest.raises(DataError):
        with db.begin_nested():
            mgr._log_event(db, t, "e" * 51, "fifty-one")
    assert len(events(db, tid)) == 0
    assert reread(db, tid) is not None


# =========================================================================== #
# _generate_tran_id
# =========================================================================== #

def test_ptm_gen_01__hex_26_no_writes(db, w1, u1):
    """PTM-GEN-01 — returns a fresh 26-char lowercase hex id and writes nothing.
    Rules: _generate_tran_id R1, R4."""
    mk_txn(db, w1, u1)
    before_t, before_e = n_txns(db), n_events(db)
    result = mgr._generate_tran_id(db)
    assert isinstance(result, str)
    assert re.fullmatch(r"[0-9a-f]{26}", result)
    assert result != A26
    assert n_txns(db) == before_t
    assert n_events(db) == before_e


def test_ptm_gen_02__uniqueness_is_global(db, w2, u2):
    """PTM-GEN-02 — a tran_id used in another workspace counts as used.
    Rules: _generate_tran_id R1."""
    mk_txn(db, w2, u2)
    with patch(PATCH_TOKEN_HEX, side_effect=[A26, B26]) as th:
        result = mgr._generate_tran_id(db)
    assert result == B26
    assert th.call_count == 2


def test_ptm_gen_03__first_candidate_free(db):
    """PTM-GEN-03 — the first unused candidate is returned after one draw.
    Rules: _generate_tran_id R2."""
    with patch(PATCH_TOKEN_HEX, side_effect=[C26, D26]) as th:
        result = mgr._generate_tran_id(db)
    assert result == C26
    assert th.call_count == 1


def test_ptm_gen_04__fifth_candidate_free(db, w1, u1):
    """PTM-GEN-04 — four collisions, the fifth draw is returned.
    Rules: _generate_tran_id R2."""
    used = [str(d) * 26 for d in range(1, 5)]
    for tid in used:
        mk_txn(db, w1, u1, tran_id=tid)
    with patch(PATCH_TOKEN_HEX, side_effect=used + ["5" * 26]) as th:
        result = mgr._generate_tran_id(db)
    assert result == "5" * 26
    assert th.call_count == 5


def test_ptm_gen_05__five_collisions_500(db, w1, u1):
    """PTM-GEN-05 — five collisions raise 500 and never draw a sixth time.
    Rules: _generate_tran_id R3, R4; Errors row 1."""
    used = [str(d) * 26 for d in range(1, 6)]
    for tid in used:
        mk_txn(db, w1, u1, tran_id=tid)
    with patch(PATCH_TOKEN_HEX, side_effect=used + ["6" * 26]) as th:
        with pytest.raises(HTTPException) as exc:
            mgr._generate_tran_id(db)
    assert exc.value.status_code == 500
    assert exc.value.detail == "Could not generate a unique transaction ID"
    assert th.call_count == 5
    assert n_txns(db) == 5
    assert n_events(db) == 0


# =========================================================================== #
# initiate_payment
# =========================================================================== #

def test_ptm_init_01__happy_path_row(db, w1, u1, gw):
    """PTM-INIT-01 — a successful session creates one INITIATED row with the request data.
    Rules: initiate_payment R5, R2."""
    res = initiate(db, w1, u1, cus_name="Karim", cus_email="karim@example.com")
    assert_returns_reread(db, res, w1.id, "INITIATED")
    gw.init_session.assert_called_once()
    req = gw_request(gw)
    assert req.cus_name == "Karim"
    assert req.cus_email == "karim@example.com"
    assert req.cus_phone == "01711000000"
    rows = txns_in(db, w1.id)
    assert len(rows) == 1
    r = rows[0]
    assert r.workspace_id == w1.id
    assert r.tran_id == req.tran_id
    assert r.status == "INITIATED"
    assert r.amount == Decimal("500.00")
    assert r.currency == "BDT"
    assert r.cus_name == "Karim"
    assert r.cus_email == "karim@example.com"
    assert r.cus_phone == "01711000000"
    assert (r.value_a, r.value_b, r.value_c, r.value_d) == (None, None, None, None)
    assert r.session_key == "SESS-1"
    assert r.gateway_page_url == "https://sandbox.example/pay/SESS-1"
    assert r.initiated_by == u1.id
    for f in ("val_id", "risk_level", "risk_title", "bank_tran_id", "card_type", "verify_sign",
              "last_ipn_payload", "validated_at", "risk_resolved_by", "risk_resolved_at",
              "risk_resolution_note"):
        assert getattr(r, f) is None, f
    assert r.initiated_at is not None
    assert r.created_at is not None
    assert r.updated_at is not None


def test_ptm_init_02__initiated_event(db, w1, u1):
    """PTM-INIT-02 — one `initiated` event with performer and session_key metadata.
    Rules: initiate_payment R6."""
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    tid = res.id
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "initiated", "Checkout session created for 500 BDT",
          performed_by=u1.id, metadata={"session_key": "SESS-1"}),
    ]


def test_ptm_init_03__amount_as_given_in_description(db, w1, u1):
    """PTM-INIT-03 — the description uses the amount as given (500.00).
    Rules: initiate_payment R6."""
    res = initiate(db, w1, u1, amount=Decimal("500.00"))
    assert_returns_reread(db, res, w1.id, "INITIATED")
    evs = events(db, res.id)
    assert len(evs) == 1
    assert evs[0].description == "Checkout session created for 500.00 BDT"


def test_ptm_init_04__no_session_key(db, w1, u1, gw):
    """PTM-INIT-04 — a SUCCESS without session_key/url stores None for both.
    Rules: initiate_payment R5, R6."""
    gw.init_session.return_value = InitSessionResult(status="SUCCESS", session_key=None, gateway_page_url=None)
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    tid = res.id
    r = reread(db, tid)
    assert r.session_key is None
    assert r.gateway_page_url is None
    assert r.status == "INITIATED"
    evs = events(db, tid)
    initiated = [e for e in evs if e.event_type == "initiated"]
    assert len(initiated) == 1
    assert initiated[0].metadata_json == {"session_key": None}


def test_ptm_init_05__name_email_default_to_profile(db, w1, u1, gw):
    """PTM-INIT-05 — omitted name/email fall back to the user's profile.
    Rules: initiate_payment R2."""
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    req = gw_request(gw)
    assert req.cus_name == "Rahim Uddin"
    assert req.cus_email == "rahim@example.com"
    r = reread(db, res.id)
    assert r.cus_name == "Rahim Uddin"
    assert r.cus_email == "rahim@example.com"


def test_ptm_init_06__empty_name_email_default_to_profile(db, w1, u1, gw):
    """PTM-INIT-06 — empty-string name/email fall back to the user's profile.
    Rules: initiate_payment R2."""
    res = initiate(db, w1, u1, cus_name="", cus_email="")
    assert_returns_reread(db, res, w1.id, "INITIATED")
    req = gw_request(gw)
    assert req.cus_name == "Rahim Uddin"
    assert req.cus_email == "rahim@example.com"
    r = reread(db, res.id)
    assert r.cus_name == "Rahim Uddin"
    assert r.cus_email == "rahim@example.com"


@xbug(BUG020)
def test_ptm_init_07__value_fields_sent_to_gateway(db, w1, u1, gw):
    """PTM-INIT-07 — value_a..d are forwarded in the gateway request.
    Rules: initiate_payment R1a [BUG-020]."""
    res = initiate(db, w1, u1, value_a="plan:pro;months:12", value_b="b-val", value_c="c-val", value_d="d-val")
    assert_returns_reread(db, res, w1.id, "INITIATED")
    req = gw_request(gw)
    assert req.value_a == "plan:pro;months:12"
    assert req.value_b == "b-val"
    assert req.value_c == "c-val"
    assert req.value_d == "d-val"


@xbug(BUG020)
def test_ptm_init_08__value_fields_none_sent(db, w1, u1, gw):
    """PTM-INIT-08 — omitted value_a..d are sent as None.
    Rules: initiate_payment R1a [BUG-020]."""
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    req = gw_request(gw)
    assert (req.value_a, req.value_b, req.value_c, req.value_d) == (None, None, None, None)


@xbug(BUG019)
def test_ptm_init_09__refused_start_recorded(db, w1, u1, gw):
    """PTM-INIT-09 — a refused session is stored as INIT_FAILED with the reason, no exception.
    Rules: initiate_payment R3 [BUG-019]."""
    gw.init_session.return_value = InitSessionResult(status="FAILED", failed_reason="Store is de-active")
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INIT_FAILED")
    req = gw_request(gw)
    rows = txns_in(db, w1.id)
    assert len(rows) == 1
    r = rows[0]
    assert r.status == "INIT_FAILED"
    assert r.failed_reason == "Store is de-active"
    assert r.tran_id == req.tran_id
    assert r.amount == Decimal("500.00")
    assert r.currency == "BDT"
    assert r.cus_name == "Rahim Uddin"
    assert r.cus_email == "rahim@example.com"
    assert r.cus_phone == "01711000000"
    assert r.initiated_by == u1.id
    assert r.session_key is None
    assert r.gateway_page_url is None
    assert r.val_id is None
    assert r.validated_at is None
    assert ev_tuples(events(db, r.id)) == [
        E(r.id, w1.id, "initiation_failed", "Checkout session refused by gateway: Store is de-active",
          performed_by=u1.id),
    ]


@xbug(BUG019)
def test_ptm_init_10__refused_no_reason(db, w1, u1, gw):
    """PTM-INIT-10 — a refusal without reason stores `unknown error`.
    Rules: initiate_payment R3 [BUG-019]."""
    gw.init_session.return_value = InitSessionResult(status="FAILED", failed_reason=None)
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INIT_FAILED")
    r = reread(db, res.id)
    assert r.status == "INIT_FAILED"
    assert r.failed_reason == "unknown error"
    assert ev_tuples(events(db, r.id)) == [
        E(r.id, w1.id, "initiation_failed", "Checkout session refused by gateway: unknown error",
          performed_by=u1.id),
    ]


@xbug(BUG019)
def test_ptm_init_11__refused_empty_reason(db, w1, u1, gw):
    """PTM-INIT-11 — a refusal with an empty reason stores `unknown error`.
    Rules: initiate_payment R3 [BUG-019]."""
    gw.init_session.return_value = InitSessionResult(status="FAILED", failed_reason="")
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INIT_FAILED")
    r = reread(db, res.id)
    assert r.failed_reason == "unknown error"
    assert r.status == "INIT_FAILED"
    evs = events(db, r.id)
    assert evs[0].description == "Checkout session refused by gateway: unknown error"


@xbug(BUG019)
def test_ptm_init_12__lowercase_success_is_refusal(db, w1, u1, gw):
    """PTM-INIT-12 — status "success" (lowercase) counts as a refusal.
    Rules: initiate_payment R3 [BUG-019]."""
    gw.init_session.return_value = InitSessionResult(
        status="success", failed_reason=None, session_key="SESS-9", gateway_page_url=None,
    )
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INIT_FAILED")
    r = reread(db, res.id)
    assert r.status == "INIT_FAILED"
    assert r.failed_reason == "unknown error"
    assert r.session_key == "SESS-9"
    assert r.gateway_page_url is None
    evs = events(db, r.id)
    assert len(evs) == 1
    assert evs[0].event_type == "initiation_failed"


def test_ptm_init_13__gateway_raises_propagates(db, w1, u1, gw):
    """PTM-INIT-13 — a gateway exception propagates unchanged; nothing is written.
    Rules: initiate_payment R4; Errors row 2."""
    err = RuntimeError("gateway down")
    gw.init_session.side_effect = err
    with pytest.raises(RuntimeError) as exc:
        initiate(db, w1, u1)
    assert exc.value is err
    assert n_txns(db, w1.id) == 0
    assert n_events(db) == 0


def test_ptm_init_14__two_calls_two_rows(db, w1, u1, gw):
    """PTM-INIT-14 — two identical requests create two distinct transactions.
    Rules: initiate_payment R7."""
    res1 = initiate(db, w1, u1)
    res2 = initiate(db, w1, u1)
    assert res1.id != res2.id
    assert [res1.id, res2.id] == ids(txns_in(db, w1.id))
    assert gw.init_session.call_count == 2
    rows = txns_in(db, w1.id)
    assert len(rows) == 2
    assert all(r.status == "INITIATED" for r in rows)
    assert rows[0].id != rows[1].id
    assert rows[0].tran_id != rows[1].tran_id
    for r in rows:
        evs = events(db, r.id)
        assert ev_types(evs) == ["initiated"]


@xbug(BUG019)
def test_ptm_init_15__failed_then_success(db, w1, u1, gw):
    """PTM-INIT-15 — a refused attempt followed by a successful one gives two rows.
    Rules: initiate_payment R7a [BUG-019]."""
    gw.init_session.side_effect = [
        InitSessionResult(status="FAILED", failed_reason="Store is de-active"),
        gw.init_session.return_value,
    ]
    res1 = initiate(db, w1, u1)
    res2 = initiate(db, w1, u1)
    assert res1.status == "INIT_FAILED"
    assert res2.status == "INITIATED"
    assert [res1.id, res2.id] == ids(txns_in(db, w1.id))
    rows = txns_in(db, w1.id)
    assert len(rows) == 2
    assert rows[0].tran_id != rows[1].tran_id
    assert sorted(r.status for r in rows) == ["INITIATED", "INIT_FAILED"]


def test_ptm_init_16__nonexistent_workspace_integrity_error(db, u1, gw):
    """PTM-INIT-16 — a nonexistent workspace fails at flush with IntegrityError after the gateway call.
    Rules: initiate_payment R8; Errors row 3."""
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            mgr.initiate_payment(db, workspace_id=999999, user=u1, request=REQ())
    assert gw.init_session.call_count == 1
    assert n_txns(db, 999999) == 0
    assert n_events(db) == 0


def test_ptm_init_17__no_unique_id_500(db, w1, w2, u1, u2, gw):
    """PTM-INIT-17 — when every candidate id is used, 500 and the gateway is never called.
    Rules: initiate_payment R1 via _generate_tran_id R3; Errors row 1."""
    mk_txn(db, w2, u2)
    with patch(PATCH_TOKEN_HEX, return_value=A26):
        with pytest.raises(HTTPException) as exc:
            initiate(db, w1, u1)
    assert exc.value.status_code == 500
    assert exc.value.detail == "Could not generate a unique transaction ID"
    gw.init_session.assert_not_called()
    assert n_txns(db, w1.id) == 0
    assert n_events(db) == 0


@xbug(BUG021)
def test_ptm_init_18__three_decimals_rejected():
    """PTM-INIT-18 — an amount with 3 decimals is rejected by the schema.
    Rules: initiate_payment R9a [BUG-021]; Errors row 4."""
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(amount=Decimal("10.005"), cus_phone="01711000000")


@xbug(BUG021)
def test_ptm_init_19__fourteen_integer_digits_rejected():
    """PTM-INIT-19 — an amount of 10^13 is rejected by the schema.
    Rules: initiate_payment R9a [BUG-021]; Errors row 4."""
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(amount=Decimal("10000000000000"), cus_phone="01711000000")


def test_ptm_init_20__valid_amounts_accepted():
    """PTM-INIT-20 — 1–2 decimals and 13 integer digits are accepted.
    Rules: initiate_payment R9, R9a boundary."""
    for value in (Decimal("10.5"), Decimal("10.50"), Decimal("9999999999999.99")):
        req = InitiatePaymentRequest(amount=value, cus_phone="01711000000")
        assert req.amount == value


@xbug(BUG022)
def test_ptm_init_21__currency_uppercased():
    """PTM-INIT-21 — "bdt" is normalised to "BDT".
    Rules: initiate_payment R10a [BUG-022]."""
    req = InitiatePaymentRequest(currency="bdt", amount=Decimal("500"), cus_phone="01711000000")
    assert req.currency == "BDT"


def test_ptm_init_22__currency_values_and_default():
    """PTM-INIT-22 — BDT and USD are kept; an omitted currency defaults to BDT.
    Rules: initiate_payment R10."""
    assert InitiatePaymentRequest(amount=Decimal("500"), currency="BDT", cus_phone="01711000000").currency == "BDT"
    assert InitiatePaymentRequest(amount=Decimal("500"), currency="USD", cus_phone="01711000000").currency == "USD"
    assert InitiatePaymentRequest(amount=Decimal("500"), cus_phone="01711000000").currency == "BDT"


@xbug(BUG022)
def test_ptm_init_23__unsupported_currency_rejected():
    """PTM-INIT-23 — "XYZ", "12 " and "EUR" are rejected.
    Rules: initiate_payment R10a [BUG-022]; Errors row 4."""
    for value in ("XYZ", "12 ", "EUR"):
        with pytest.raises(ValidationError):
            InitiatePaymentRequest(amount=Decimal("500"), currency=value, cus_phone="01711000000")


@xbug(BUG022)
def test_ptm_init_24__lowercase_currency_end_to_end(db, w1, u1, gw):
    """PTM-INIT-24 — "bdt" reaches the gateway, row and event as "BDT".
    Rules: initiate_payment R10a [BUG-022]."""
    res = initiate(db, w1, u1, request=InitiatePaymentRequest(
        amount=Decimal("500"), currency="bdt", cus_phone="01711000000"))
    assert_returns_reread(db, res, w1.id, "INITIATED")
    assert gw_request(gw).currency == "BDT"
    assert reread(db, res.id).currency == "BDT"
    assert events(db, res.id)[0].description == "Checkout session created for 500 BDT"


def test_ptm_init_25__gateway_request_shape(db, w1, u1, gw):
    """PTM-INIT-25 — the gateway request carries id, amount, URLs, customer and product; value_* stored.
    Rules: initiate_payment R1, R5."""
    res = initiate(db, w1, u1, value_a="plan:pro;months:12", value_b="b-val", value_c="c-val", value_d="d-val")
    assert_returns_reread(db, res, w1.id, "INITIATED")
    gw.init_session.assert_called_once()
    assert len(gw.init_session.call_args.args) == 1
    assert gw.init_session.call_args.kwargs == {}
    req = gw_request(gw)
    r = reread(db, res.id)
    assert re.fullmatch(r"[0-9a-f]{26}", req.tran_id)
    assert req.tran_id == r.tran_id
    assert req.amount == Decimal("500")
    assert req.currency == "BDT"
    base = f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments"
    assert req.success_url == f"{base}/success"
    assert req.fail_url == f"{base}/fail"
    assert req.cancel_url == f"{base}/cancel"
    assert req.ipn_url == f"{base}/ipn"
    assert req.cus_name == "Rahim Uddin"
    assert req.cus_email == "rahim@example.com"
    assert req.cus_phone == "01711000000"
    assert req.product_name == "Workspace Subscription"
    assert req.product_category == "subscription"
    assert r.value_a == "plan:pro;months:12"
    assert r.value_b == "b-val"
    assert r.value_c == "c-val"
    assert r.value_d == "d-val"


def test_ptm_init_26__amount_must_be_positive():
    """PTM-INIT-26 — 0 and -1 are rejected, 0.01 is accepted.
    Rules: initiate_payment R9."""
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(amount=Decimal("0"), cus_phone="01711000000")
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(amount=Decimal("-1"), cus_phone="01711000000")
    req = InitiatePaymentRequest(amount=Decimal("0.01"), cus_phone="01711000000")
    assert req.amount == Decimal("0.01")


def test_ptm_init_27__amount_sent_as_given_stored_2dp(db, w1, u1, gw):
    """PTM-INIT-27 — 10.5 goes to the gateway and event as "10.5" and is stored as 10.50.
    Rules: initiate_payment R9."""
    res = initiate(db, w1, u1, amount=Decimal("10.5"))
    assert_returns_reread(db, res, w1.id, "INITIATED")
    req = gw_request(gw)
    assert req.amount == Decimal("10.5")
    assert str(req.amount) == "10.5"
    assert reread(db, res.id).amount == Decimal("10.50")
    assert events(db, res.id)[0].description == "Checkout session created for 10.5 BDT"


def test_ptm_init_28__largest_amount(db, w1, u1, gw):
    """PTM-INIT-28 — 9999999999999.99 is sent and stored without error.
    Rules: initiate_payment R9."""
    res = initiate(db, w1, u1, amount=Decimal("9999999999999.99"))
    assert_returns_reread(db, res, w1.id, "INITIATED")
    assert gw_request(gw).amount == Decimal("9999999999999.99")
    assert reread(db, res.id).amount == Decimal("9999999999999.99")


def test_ptm_init_29__usd(db, w1, u1, gw):
    """PTM-INIT-29 — USD is used for the gateway, row and event.
    Rules: initiate_payment R10."""
    res = initiate(db, w1, u1, currency="USD")
    assert_returns_reread(db, res, w1.id, "INITIATED")
    assert gw_request(gw).currency == "USD"
    assert reread(db, res.id).currency == "USD"
    assert events(db, res.id)[0].description == "Checkout session created for 500 USD"


@xbug(BUG019)
def test_ptm_init_30__failed_reason_none_on_success(db, w1, u1):
    """PTM-INIT-30 — a successful start stores failed_reason None.
    Rules: initiate_payment R5a [BUG-019]."""
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    assert reread(db, res.id).failed_reason is None


@xbug(BUG026)
def test_ptm_init_31__new_txn_unverified(db, w1, u1):
    """PTM-INIT-31 — a new transaction starts with outcome_verified False.
    Rules: _apply R12 [BUG-026]."""
    res = initiate(db, w1, u1)
    assert_returns_reread(db, res, w1.id, "INITIATED")
    assert reread(db, res.id).outcome_verified is False


# =========================================================================== #
# _apply_validation_result
# =========================================================================== #

@pytest.fixture
def t(db, w1, u1):
    """Convention "T" for the AVR section: W1, INITIATED, 500.00 BDT."""
    return mk_txn(db, w1, u1)


def test_ptm_avr_01__valid_success(db, w1, t, gw):
    """PTM-AVR-01 — a matching VALID answer gives VALIDATED_SUCCESS with gateway fields.
    Rules: _apply_validation_result R10, R3."""
    tid = t.id
    ret = apply_(db, t, OK)
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.validated_at == NOW
    assert gw_fields(r) == OK_FIELDS
    assert r.updated_at != UPD0
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "validated_success", "Validated successfully via ipn callback"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_avr_02__risk_level_none_success(db, t, gw):
    """PTM-AVR-02 — risk_level None counts as not risky.
    Rules: _apply_validation_result R10."""
    tid = t.id
    ret = apply_(db, t, ok(risk_level=None))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


def test_ptm_avr_03__risk_level_2_success(db, t, gw):
    """PTM-AVR-03 — risk_level 2 counts as not risky.
    Rules: _apply_validation_result R10."""
    tid = t.id
    ret = apply_(db, t, ok(risk_level=2))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.risk_level == 2
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


def test_ptm_avr_04__risk_level_1_hold(db, w1, t, gw):
    """PTM-AVR-04 — risk_level 1 puts the transaction in RISK_HOLD.
    Rules: _apply_validation_result R9."""
    tid = t.id
    ret = apply_(db, t, ok(risk_level=1, risk_title="Suspicious card"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.validated_at == NOW
    assert r.risk_level == 1
    assert r.risk_title == "Suspicious card"
    assert ev_tuples(events(db, tid)) == [E(tid, w1.id, "risk_hold", HIGH_RISK_DESC)]
    assert_no_gateway_calls(gw)


def test_ptm_avr_05__risk_hold_title_none(db, t, gw):
    """PTM-AVR-05 — a missing risk_title reads "None" in the description.
    Rules: _apply_validation_result R9."""
    tid = t.id
    ret = apply_(db, t, ok(risk_level=1, risk_title=None))
    assert ret is t
    assert reread(db, tid).status == "RISK_HOLD"
    assert events(db, tid)[0].description == (
        "Validated via ipn callback but flagged high-risk (None) — held for review")
    assert_no_gateway_calls(gw)


def test_ptm_avr_06__empty_tran_id_skips_check(db, t, gw):
    """PTM-AVR-06 — an empty result tran_id skips the tran_id check.
    Rules: _apply_validation_result R2."""
    tid = t.id
    ret = apply_(db, t, ok(tran_id=""))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


@xbug(BUG023)
def test_ptm_avr_07__foreign_tran_id_rejected(db, t, gw):
    """PTM-AVR-07 — a val_id resolving to another tran_id changes nothing.
    Rules: _apply_validation_result R1a [BUG-023]."""
    tid = t.id
    ret = apply_(db, t, ok(tran_id=B26))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert r.updated_at == UPD0
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "validation_rejected"
    assert_no_gateway_calls(gw)


@xbug(BUG023)
def test_ptm_avr_08__uppercase_tran_id_rejected(db, t, gw):
    """PTM-AVR-08 — an upper-cased tran_id is a foreign tran_id.
    Rules: _apply_validation_result R1a [BUG-023]."""
    tid = t.id
    ret = apply_(db, t, ok(tran_id="A" * 26))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "validation_rejected"
    assert_no_gateway_calls(gw)


@xbug(BUG023)
def test_ptm_avr_09__invalid_foreign_rejected(db, t, gw):
    """PTM-AVR-09 — INVALID_TRANSACTION with a foreign tran_id changes nothing.
    Rules: _apply_validation_result R1a, R2a [BUG-023]."""
    tid = t.id
    ret = apply_(db, t, invalid(B26))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "validation_rejected"
    assert_no_gateway_calls(gw)


@xbug(BUG023)
def test_ptm_avr_10__foreign_on_expired_rejected(db, w1, u1, gw):
    """PTM-AVR-10 — a foreign tran_id leaves an EXPIRED row unchanged.
    Rules: _apply_validation_result R1a [BUG-023], R11."""
    t = mk_txn(db, w1, u1, status="EXPIRED", validated_at=V0, val_id="OLD-VAL", bank_tran_id="OLD-BANK")
    tid = t.id
    ret = apply_(db, t, ok(tran_id=B26))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "EXPIRED"
    assert r.validated_at == V0
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "validation_rejected"
    assert_no_gateway_calls(gw)


@xbug(BUG023)
def test_ptm_avr_11__invalid_transaction_rejected(db, w1, t, gw):
    """PTM-AVR-11 — INVALID_TRANSACTION (empty tran_id) changes nothing and logs a rejection.
    Rules: _apply_validation_result R2a [BUG-023]."""
    tid = t.id
    ret = apply_(db, t, invalid(""))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert gw_fields(r) == NONE_FIELDS
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "validation_rejected",
          "Gateway validation via ipn callback returned status=INVALID_TRANSACTION; val_id rejected"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_avr_12__status_failed(db, w1, t, gw):
    """PTM-AVR-12 — gateway status FAILED gives VALIDATED_FAILED with fields copied.
    Rules: _apply_validation_result R4, R3."""
    tid = t.id
    ret = apply_(db, t, ok(status="FAILED"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert gw_fields(r) == OK_FIELDS
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "validated_failed", "Gateway validation via ipn callback returned status=FAILED"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_avr_13__status_case_sensitive(db, t, gw):
    """PTM-AVR-13 — lowercase "valid" is not a success status.
    Rules: _apply_validation_result R4."""
    tid = t.id
    ret = apply_(db, t, ok(status="valid"))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_FAILED"
    assert events(db, tid)[0].description == "Gateway validation via ipn callback returned status=valid"
    assert_no_gateway_calls(gw)


def test_ptm_avr_14__status_validated_success(db, t, gw):
    """PTM-AVR-14 — gateway status VALIDATED counts as success.
    Rules: _apply_validation_result R4, R10."""
    tid = t.id
    ret = apply_(db, t, ok(status="VALIDATED"))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


@xbug(BUG025)
def test_ptm_avr_15__gateway_cancelled(db, t, gw):
    """PTM-AVR-15 — gateway status CANCELLED gives CANCELLED.
    Rules: _apply_validation_result R4b [BUG-025]."""
    tid = t.id
    ret = apply_(db, t, ok(status="CANCELLED"))
    assert ret is t
    assert reread(db, tid).status == "CANCELLED"
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "validated_cancelled"
    assert_no_gateway_calls(gw)


def test_ptm_avr_16__none_fields_overwrite(db, w1, u1, gw):
    """PTM-AVR-16 — None gateway fields overwrite old values.
    Rules: _apply_validation_result R3, R11."""
    t = mk_txn(db, w1, u1, status="EXPIRED", val_id="OLD-VAL", risk_level=0, risk_title="Old",
               bank_tran_id="OLD-BANK", card_type="OLD-CARD", verify_sign="OLD-SIG")
    tid = t.id
    ret = apply_(db, t, ValidationResult(status="FAILED", tran_id=A26, amount=Decimal("500.00"), currency="BDT"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert gw_fields(r) == NONE_FIELDS
    assert_no_gateway_calls(gw)


def test_ptm_avr_17__amount_mismatch(db, w1, t, gw):
    """PTM-AVR-17 — a different amount gives VALIDATED_FAILED with fields copied.
    Rules: _apply_validation_result R5."""
    tid = t.id
    ret = apply_(db, t, ok(amount=Decimal("499.99")))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert gw_fields(r) == OK_FIELDS
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "validated_failed", "Amount mismatch: expected 500.00 BDT, gateway reported 499.99 BDT"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_avr_18__amount_numeric_equality(db, t, gw):
    """PTM-AVR-18 — 500 equals 500.00.
    Rules: _apply_validation_result R5."""
    tid = t.id
    ret = apply_(db, t, ok(amount=Decimal("500")))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    assert_no_gateway_calls(gw)


def test_ptm_avr_19__amount_checked_before_missing_currency(db, t, gw):
    """PTM-AVR-19 — an amount mismatch wins over a missing currency.
    Rules: _apply_validation_result R5, R8 order."""
    tid = t.id
    ret = apply_(db, t, ok(amount=Decimal("400"), currency=None))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_FAILED"
    assert events(db, tid)[0].description == "Amount mismatch: expected 500.00 BDT, gateway reported 400 None"
    assert_no_gateway_calls(gw)


def test_ptm_avr_20__amount_checked_before_currency(db, t, gw):
    """PTM-AVR-20 — an amount mismatch wins over a currency mismatch.
    Rules: _apply_validation_result R5, R7 order."""
    tid = t.id
    ret = apply_(db, t, ok(amount=Decimal("400"), currency="USD"))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_FAILED"
    assert events(db, tid)[0].description == "Amount mismatch: expected 500.00 BDT, gateway reported 400 USD"
    assert_no_gateway_calls(gw)


def test_ptm_avr_21__currency_mismatch(db, w1, t, gw):
    """PTM-AVR-21 — a different currency gives VALIDATED_FAILED with fields copied.
    Rules: _apply_validation_result R7."""
    tid = t.id
    ret = apply_(db, t, ok(currency="USD"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert gw_fields(r) == OK_FIELDS
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "validated_failed", "Currency mismatch: expected BDT, gateway reported USD"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_avr_22__currency_case_sensitive(db, t, gw):
    """PTM-AVR-22 — "bdt" does not match "BDT".
    Rules: _apply_validation_result R7."""
    tid = t.id
    ret = apply_(db, t, ok(currency="bdt"))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_FAILED"
    assert events(db, tid)[0].description == "Currency mismatch: expected BDT, gateway reported bdt"
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_23__missing_amount_hold(db, w1, t, gw):
    """PTM-AVR-23 — a VALID answer without amount goes to RISK_HOLD.
    Rules: _apply_validation_result R6 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(amount=None))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.validated_at == NOW
    assert gw_fields(r) == OK_FIELDS
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "risk_hold", "Validated via ipn callback but gateway reported no amount — held for review"),
    ]
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_24__missing_amount_text_over_risk(db, t, gw):
    """PTM-AVR-24 — missing amount text wins over the high-risk text.
    Rules: _apply_validation_result R6 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(amount=None, risk_level=1, risk_title="Suspicious card"))
    assert ret is t
    assert reread(db, tid).status == "RISK_HOLD"
    assert events(db, tid)[0].description == (
        "Validated via ipn callback but gateway reported no amount — held for review")
    assert_no_gateway_calls(gw)


def test_ptm_avr_25__currency_mismatch_over_missing_amount(db, t, gw):
    """PTM-AVR-25 — a currency mismatch fails even when the amount is missing.
    Rules: _apply_validation_result R7 over R6."""
    tid = t.id
    ret = apply_(db, t, ok(amount=None, currency="USD"))
    assert ret is t
    assert reread(db, tid).status == "VALIDATED_FAILED"
    assert events(db, tid)[0].description == "Currency mismatch: expected BDT, gateway reported USD"
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_26__missing_currency_hold(db, w1, t, gw):
    """PTM-AVR-26 — a VALID answer without currency goes to RISK_HOLD.
    Rules: _apply_validation_result R8 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(currency=None))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.validated_at == NOW
    assert ev_tuples(events(db, tid)) == [
        E(tid, w1.id, "risk_hold", "Validated via ipn callback but gateway reported no currency — held for review"),
    ]
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_27__empty_currency_hold(db, t, gw):
    """PTM-AVR-27 — an empty currency counts as missing.
    Rules: _apply_validation_result R8 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(currency=""))
    assert ret is t
    assert reread(db, tid).status == "RISK_HOLD"
    assert events(db, tid)[0].description == (
        "Validated via ipn callback but gateway reported no currency — held for review")
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_28__missing_currency_text_over_risk(db, t, gw):
    """PTM-AVR-28 — missing currency text wins over the high-risk text.
    Rules: _apply_validation_result R8 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(currency=None, risk_level=1, risk_title="Suspicious card"))
    assert ret is t
    assert reread(db, tid).status == "RISK_HOLD"
    assert events(db, tid)[0].description == (
        "Validated via ipn callback but gateway reported no currency — held for review")
    assert_no_gateway_calls(gw)


@xbug(BUG024)
def test_ptm_avr_29__missing_both_amount_text(db, t, gw):
    """PTM-AVR-29 — both missing: one event with the missing-amount text.
    Rules: _apply_validation_result R6, R8 [BUG-024]."""
    tid = t.id
    ret = apply_(db, t, ok(amount=None, currency=None))
    assert ret is t
    assert reread(db, tid).status == "RISK_HOLD"
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == "Validated via ipn callback but gateway reported no amount — held for review"
    assert_no_gateway_calls(gw)


def test_ptm_avr_30__expired_row_finalized(db, w1, u1, gw):
    """PTM-AVR-30 — the helper finalizes an EXPIRED row.
    Rules: _apply_validation_result R11."""
    t = mk_txn(db, w1, u1, status="EXPIRED", validated_at=V0)
    tid = t.id
    ret = apply_(db, t, OK)
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.validated_at == NOW
    assert r.val_id == "VAL-1"
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


def test_ptm_avr_31__cancelled_row_finalized(db, w1, u1, gw):
    """PTM-AVR-31 — the helper finalizes a CANCELLED row.
    Rules: _apply_validation_result R11."""
    t = mk_txn(db, w1, u1, status="CANCELLED", validated_at=V0)
    tid = t.id
    ret = apply_(db, t, OK)
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.validated_at == NOW
    assert ev_types(events(db, tid)) == ["validated_success"]
    assert_no_gateway_calls(gw)


def test_ptm_avr_32__foreign_tran_id_not_applied(db, t, gw):
    """PTM-AVR-32 — a foreign tran_id never copies fields or succeeds.
    Rules: _apply_validation_result R1."""
    tid = t.id
    ret = apply_(db, t, ok(tran_id=B26))
    assert ret is t
    r = reread(db, tid)
    assert gw_fields(r) == NONE_FIELDS
    assert r.val_id != "VAL-1"
    assert r.status not in {"VALIDATED_SUCCESS", "RISK_HOLD"}
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"
    assert_no_gateway_calls(gw)


def test_ptm_avr_33__uppercase_tran_id_is_foreign(db, t, gw):
    """PTM-AVR-33 — the tran_id comparison is case-sensitive.
    Rules: _apply_validation_result R1."""
    tid = t.id
    ret = apply_(db, t, ok(tran_id="A" * 26))
    assert ret is t
    r = reread(db, tid)
    assert r.val_id is None
    assert r.bank_tran_id is None
    assert r.status not in {"VALIDATED_SUCCESS", "RISK_HOLD"}
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == (
        f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={'A' * 26}")
    assert_no_gateway_calls(gw)


def test_ptm_avr_34__foreign_keeps_old_fields(db, w1, u1, gw):
    """PTM-AVR-34 — a foreign tran_id leaves existing gateway fields untouched.
    Rules: _apply_validation_result R1, R11."""
    t = mk_txn(db, w1, u1, status="EXPIRED", validated_at=V0, val_id="OLD-VAL", bank_tran_id="OLD-BANK")
    tid = t.id
    ret = apply_(db, t, ok(tran_id=B26))
    assert ret is t
    r = reread(db, tid)
    assert r.val_id == "OLD-VAL"
    assert r.bank_tran_id == "OLD-BANK"
    assert r.risk_level is None
    assert r.risk_title is None
    assert r.card_type is None
    assert r.verify_sign is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"
    assert_no_gateway_calls(gw)


def test_ptm_avr_35__tran_id_checked_first(db, t, gw):
    """PTM-AVR-35 — the tran_id check runs before the INVALID_TRANSACTION check.
    Rules: _apply_validation_result R1 before R2a."""
    tid = t.id
    ret = apply_(db, t, ValidationResult(status="INVALID_TRANSACTION", tran_id=B26, val_id="VAL-X"))
    assert ret is t
    r = reread(db, tid)
    assert r.val_id is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"
    assert_no_gateway_calls(gw)


def test_ptm_avr_36__cancelled_copies_fields_skips_checks(db, t, gw):
    """PTM-AVR-36 — CANCELLED copies fields and skips amount/risk checks.
    Rules: _apply_validation_result R4a, R3."""
    tid = t.id
    ret = apply_(db, t, ok(status="CANCELLED", amount=Decimal("1"), risk_level=1, risk_title="Suspicious card"))
    assert ret is t
    r = reread(db, tid)
    assert r.validated_at == NOW
    assert gw_fields(r) == ("VAL-1", 1, "Suspicious card", "BANK-1", "VISA-Brac bank", "SIG-1")
    assert r.status not in {"INITIATED", "VALIDATED_SUCCESS", "RISK_HOLD"}
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == "Gateway validation via ipn callback returned status=CANCELLED"
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_avr_37__success_marks_verified(db, t, gw):
    """PTM-AVR-37 — a success sets outcome_verified True.
    Rules: _apply_validation_result R12 [BUG-026]."""
    tid = t.id
    ret = apply_(db, t, OK)
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.outcome_verified is True
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_avr_38__failure_marks_verified(db, t, gw):
    """PTM-AVR-38 — a gateway failure sets outcome_verified True.
    Rules: _apply_validation_result R12 [BUG-026]."""
    tid = t.id
    ret = apply_(db, t, ok(status="FAILED"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.outcome_verified is True
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_avr_39__risk_hold_marks_verified(db, t, gw):
    """PTM-AVR-39 — RISK_HOLD sets outcome_verified True.
    Rules: _apply_validation_result R12 [BUG-026]."""
    tid = t.id
    ret = apply_(db, t, ok(risk_level=1, risk_title="Suspicious card"))
    assert ret is t
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.outcome_verified is True
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_avr_40__unverified_cancel_replaced_verified(db, w1, u1, gw):
    """PTM-AVR-40 — an unverified CANCELLED replaced by success becomes verified.
    Rules: _apply_validation_result R12 [BUG-026]."""
    t = mk_txn(db, w1, u1, status="CANCELLED", validated_at=V0, outcome_verified=False)
    tid = t.id
    ret = apply_(db, t, OK)
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.outcome_verified is True
    assert_no_gateway_calls(gw)


@xbug(BUG026, BUG023)
def test_ptm_avr_41__rejection_keeps_marker_true(db, w1, u1, gw):
    """PTM-AVR-41 — a rejection leaves outcome_verified True unchanged.
    Rules: _apply_validation_result R12 [BUG-026] (needs BUG-023 too)."""
    t = mk_txn(db, w1, u1, outcome_verified=True)
    tid = t.id
    ret = apply_(db, t, ok(tran_id=B26))
    assert ret is t
    assert reread(db, tid).outcome_verified is True
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_avr_42__default_unverified(db, t, gw):
    """PTM-AVR-42 — a row inserted without the marker reads outcome_verified False.
    Rules: _apply_validation_result R12 [BUG-026]."""
    tid = t.id
    assert reread(db, tid).outcome_verified is False
    assert_no_gateway_calls(gw)


@xbug(BUG026, BUG023)
def test_ptm_avr_43__rejection_keeps_marker_false(db, w1, u1, gw):
    """PTM-AVR-43 — a rejection leaves outcome_verified False unchanged.
    Rules: _apply_validation_result R12 [BUG-026] (needs BUG-023 too)."""
    t = mk_txn(db, w1, u1, outcome_verified=False)
    tid = t.id
    ret = apply_(db, t, invalid(""))
    assert ret is t
    assert reread(db, tid).outcome_verified is False
    assert_no_gateway_calls(gw)


# =========================================================================== #
# finalize_from_gateway  (T is in W2)
# =========================================================================== #

@pytest.fixture
def t2(db, w2, u2):
    """Convention "T in W2" for the FIN / MTW sections."""
    return mk_txn(db, w2, u2)


def test_ptm_fin_01__ipn_success(db, w2, t2, gw):
    """PTM-FIN-01 — an IPN for an INITIATED row is validated and finalized.
    Rules: finalize_from_gateway R1, R4."""
    tid = t2.id
    ret = fin(db)
    assert ret is t2
    gw.validate.assert_called_once_with("VAL-1")
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert r.validated_at == NOW
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "ipn_received", "Callback received via ipn"),
        E(tid, w2.id, "validated_success", "Validated successfully via ipn callback"),
    ]


def test_ptm_fin_02__lookup_locks_row(db, engine, t2):
    """PTM-FIN-02 — the lookup is SELECT ... FOR UPDATE.
    Rules: finalize_from_gateway R1."""
    with SqlCapture(engine) as cap:
        ret = fin(db)
    assert ret is t2
    assert cap.has_select_for_update_on_txns()


def test_ptm_fin_03__unknown_tran_id_404(db, t2, gw):
    """PTM-FIN-03 — an unknown tran_id raises 404 and writes nothing.
    Rules: finalize_from_gateway R2; Errors row 1."""
    tid = t2.id
    with pytest.raises(HTTPException) as exc:
        fin(db, tran_id="z" * 26)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Unknown tran_id: {'z' * 26}"
    gw.validate.assert_not_called()
    assert n_events(db) == 0
    assert reread(db, tid).status == "INITIATED"


@xbug(BUG028)
def test_ptm_fin_04__redirect_success_event_type(db, t2):
    """PTM-FIN-04 — the received event for redirect_success is typed `redirect_success`.
    Rules: finalize_from_gateway R4a [BUG-028]."""
    tid = t2.id
    ret = fin(db, source="redirect_success")
    assert ret is t2
    assert events(db, tid)[0].event_type == "redirect_success"


@xbug(BUG028)
def test_ptm_fin_05__redirect_fail_event_type(db, t2, gw):
    """PTM-FIN-05 — the received event for redirect_fail is typed `redirect_fail`.
    Rules: finalize_from_gateway R4a [BUG-028]."""
    gw.validate.return_value = ok(status="FAILED")
    tid = t2.id
    ret = fin(db, source="redirect_fail")
    assert ret is t2
    assert events(db, tid)[0].event_type == "redirect_fail"


@xbug(BUG023)
def test_ptm_fin_06__foreign_val_id_ignored(db, t2, gw):
    """PTM-FIN-06 — a val_id resolving to another tran_id leaves the row INITIATED.
    Rules: finalize_from_gateway R4, _apply R1a [BUG-023]."""
    gw.validate.return_value = ok(tran_id=B26)
    tid = t2.id
    ret = fin(db)
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert events(db, tid)[1].event_type == "validation_rejected"


def test_ptm_fin_07__duplicate_on_success(db, w2, u2, gw):
    """PTM-FIN-07 — a callback for a VALIDATED_SUCCESS row is ignored as a duplicate.
    Rules: finalize_from_gateway R3."""
    t = mk_txn(db, w2, u2, status="VALIDATED_SUCCESS", val_id="VAL-ORIG", validated_at=V0)
    tid = t.id
    ret = fin(db, val_id="VAL-NEW")
    assert ret is t
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-ORIG"
    assert r.validated_at == V0
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_SUCCESS"),
    ]


def test_ptm_fin_08__duplicate_on_risk_hold(db, w2, t2, gw):
    """PTM-FIN-08 — a callback for a RISK_HOLD row is ignored as a duplicate.
    Rules: finalize_from_gateway R3."""
    tid = t2.id
    to_risk_hold(db, t2)
    n_setup = len(events(db, tid))
    gw.validate.return_value = ok(val_id="VAL-NEW")
    ret = fin(db, val_id="VAL-NEW")
    assert ret is t2
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.val_id == "VAL-1"
    assert ev_tuples(events(db, tid)[n_setup:]) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already RISK_HOLD"),
    ]


def test_ptm_fin_09__duplicate_on_init_failed(db, w2, u2, gw):
    """PTM-FIN-09 — a callback for an INIT_FAILED row is ignored as a duplicate.
    Rules: finalize_from_gateway R3."""
    t = mk_txn(db, w2, u2, status="INIT_FAILED")
    tid = t.id
    ret = fin(db)
    assert ret is t
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "INIT_FAILED"
    assert r.val_id is None
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already INIT_FAILED"),
    ]


def test_ptm_fin_10__verified_failure_final(db, w2, t2, gw):
    """PTM-FIN-10 — a gateway-verified VALIDATED_FAILED is final.
    Rules: finalize_from_gateway R3, R5."""
    tid = t2.id
    gw.validate.return_value = ok(status="FAILED")
    fin(db)
    n_setup = len(events(db, tid))
    gw.validate.return_value = ok(val_id="VAL-2")
    ret = fin(db, val_id="VAL-2")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.val_id == "VAL-1"
    assert gw.validate.call_count == 1
    assert ev_tuples(events(db, tid)[n_setup:]) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"),
    ]


@xbug(BUG025)
def test_ptm_fin_11__verified_cancel_final_as_cancelled(db, t2, gw):
    """PTM-FIN-11 — a gateway-verified CANCELLED stays CANCELLED; later callback is a duplicate.
    Rules: finalize_from_gateway R3c [BUG-025]."""
    tid = t2.id
    gw.validate.return_value = ok(status="CANCELLED")
    fin(db)
    n_setup = len(events(db, tid))
    gw.validate.return_value = OK
    ret = fin(db, val_id="VAL-2")
    assert ret is t2
    assert reread(db, tid).status == "CANCELLED"
    assert events(db, tid)[n_setup].description == (
        "Duplicate ipn callback ignored; transaction already CANCELLED")


def test_ptm_fin_12__rejected_risk_final(db, w2, u2, t2, gw):
    """PTM-FIN-12 — a risk hold rejected by the owner is final.
    Rules: finalize_from_gateway R3; resolve_risk R3."""
    tid = t2.id
    to_risk_hold(db, t2)
    rr(db, tid, w2.id, u2.id, False, "Fraud")
    n_setup = len(events(db, tid))
    ret = fin(db)
    assert ret is t2
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.risk_resolution_note == "Fraud"
    assert r.val_id == "VAL-1"
    assert ev_tuples(events(db, tid)[n_setup:]) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"),
    ]


def test_ptm_fin_13__second_callback_duplicate(db, w2, t2, gw):
    """PTM-FIN-13 — the second callback after a success is a duplicate.
    Rules: finalize_from_gateway R5."""
    tid = t2.id
    gw.validate.side_effect = [OK, ok(val_id="VAL-2")]
    ret1 = fin(db, val_id="VAL-1")
    ret2 = fin(db, val_id="VAL-2")
    assert ret1 is t2
    assert ret2 is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert gw.validate.call_count == 1
    evs = events(db, tid)
    assert ev_types(evs) == ["ipn_received", "validated_success", "duplicate_ignored"]
    assert ev_tuples(evs[2:]) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_SUCCESS"),
    ]


@xbug(BUG023)
def test_ptm_fin_14__rejected_then_genuine(db, t2, gw):
    """PTM-FIN-14 — after a rejected val_id, a genuine one still finalizes.
    Rules: finalize_from_gateway R5a [BUG-023]."""
    tid = t2.id
    gw.validate.side_effect = [invalid(""), ok(val_id="VAL-2")]
    ret1 = fin(db, val_id="VAL-X")
    assert ret1 is t2
    assert reread(db, tid).status == "INITIATED"
    ret2 = fin(db, val_id="VAL-2")
    assert ret2 is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-2"
    assert gw.validate.call_args_list == [call("VAL-X"), call("VAL-2")]
    assert ev_types(events(db, tid)) == ["ipn_received", "validation_rejected", "ipn_received", "validated_success"]


@xbug(BUG026)
def test_ptm_fin_15__verified_replaces_unverified_cancel(db, w2, t2, gw):
    """PTM-FIN-15 — a verified IPN replaces an unverified cancel redirect.
    Rules: finalize_from_gateway R3a [BUG-026]."""
    tid = t2.id
    mtw(db, "CANCELLED", "redirect_cancel")
    n_setup = len(events(db, tid))
    ret = fin(db)
    assert ret is t2
    gw.validate.assert_called_once_with("VAL-1")
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert r.validated_at == NOW
    assert r.outcome_verified is True
    assert ev_tuples(events(db, tid)[n_setup:]) == [
        E(tid, w2.id, "ipn_received", "Callback received via ipn"),
        E(tid, w2.id, "validated_success", "Validated successfully via ipn callback"),
    ]


@xbug(BUG026)
def test_ptm_fin_16__verified_replaces_unverified_fail(db, t2, gw):
    """PTM-FIN-16 — a verified IPN replaces an unverified fail redirect.
    Rules: finalize_from_gateway R3a [BUG-026]."""
    tid = t2.id
    mtw(db, "VALIDATED_FAILED", "redirect_fail_no_val_id")
    n_setup = len(events(db, tid))
    ret = fin(db)
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert ev_types(events(db, tid)[n_setup:]) == ["ipn_received", "validated_success"]


@xbug(BUG026)
def test_ptm_fin_17__rejection_keeps_unverified_replaceable(db, t2, gw):
    """PTM-FIN-17 — a rejected val_id on an unverified cancel keeps it replaceable.
    Rules: finalize_from_gateway R3a [BUG-026], _apply R2a."""
    tid = t2.id
    mtw(db, "CANCELLED", "redirect_cancel")
    n_setup = len(events(db, tid))
    gw.validate.side_effect = [invalid(""), OK]
    ret1 = fin(db, val_id="VAL-X")
    assert ret1 is t2
    r = reread(db, tid)
    assert r.status == "CANCELLED"
    assert r.val_id is None
    assert ev_types(events(db, tid)[n_setup:]) == ["ipn_received", "validation_rejected"]
    ret2 = fin(db, val_id="VAL-1")
    assert ret2 is t2
    assert reread(db, tid).status == "VALIDATED_SUCCESS"


@xbug(BUG026)
def test_ptm_fin_18__verified_failure_replaces_then_final(db, w2, t2, gw):
    """PTM-FIN-18 — a verified failure replaces an unverified cancel and is then final.
    Rules: finalize_from_gateway R3a [BUG-026], R3."""
    tid = t2.id
    mtw(db, "CANCELLED", "redirect_cancel")
    gw.validate.side_effect = [ok(status="FAILED"), OK]
    ret1 = fin(db, val_id="VAL-1")
    assert ret1 is t2
    assert reread(db, tid).status == "VALIDATED_FAILED"
    ret2 = fin(db, val_id="VAL-2")
    assert ret2 is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.val_id == "VAL-1"
    assert ev_tuples(events(db, tid)[-1:]) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"),
    ]
    assert gw.validate.call_count == 1


@xbug(BUG027)
def test_ptm_fin_19__verified_replaces_expired(db, w2, u2, gw):
    """PTM-FIN-19 — a verified IPN replaces EXPIRED.
    Rules: finalize_from_gateway R3b [BUG-027]."""
    t = mk_txn(db, w2, u2, status="EXPIRED", validated_at=V0)
    tid = t.id
    ret = fin(db)
    assert ret is t
    gw.validate.assert_called_once()
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.validated_at == NOW
    assert r.val_id == "VAL-1"
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "ipn_received", "Callback received via ipn"),
        E(tid, w2.id, "validated_success", "Validated successfully via ipn callback"),
    ]


def test_ptm_fin_20__validate_raises_propagates(db, w2, t2, gw):
    """PTM-FIN-20 — a gateway exception propagates; only the received event exists.
    Rules: finalize_from_gateway R6; Errors row 2."""
    tid = t2.id
    err = RuntimeError("gateway timeout")
    gw.validate.side_effect = err
    with pytest.raises(RuntimeError) as exc:
        fin(db)
    assert exc.value is err
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert gw_fields(r) == NONE_FIELDS
    assert ev_tuples(events(db, tid)) == [E(tid, w2.id, "ipn_received", "Callback received via ipn")]


@xbug(BUG026)
def test_ptm_fin_21__unmarked_cancelled_is_replaceable(db, w2, u2, gw):
    """PTM-FIN-21 — a CANCELLED row without marker counts as unverified.
    Rules: finalize_from_gateway R3a [BUG-026]."""
    t = mk_txn(db, w2, u2, status="CANCELLED", validated_at=V0)
    tid = t.id
    ret = fin(db)
    assert ret is t
    gw.validate.assert_called_once()
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert r.validated_at == NOW
    assert ev_types(events(db, tid)) == ["ipn_received", "validated_success"]


@xbug(BUG026)
def test_ptm_fin_22__verified_failed_row_final(db, w2, u2, gw):
    """PTM-FIN-22 — a VALIDATED_FAILED row marked verified is final.
    Rules: finalize_from_gateway R3 [BUG-026 setup]."""
    t = mk_txn(db, w2, u2, status="VALIDATED_FAILED", outcome_verified=True, val_id="VAL-ORIG", validated_at=V0)
    tid = t.id
    ret = fin(db, val_id="VAL-NEW")
    assert ret is t
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.val_id == "VAL-ORIG"
    assert r.validated_at == V0
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"),
    ]


@xbug(BUG026)
def test_ptm_fin_23__verified_risk_hold_final(db, w2, u2, gw):
    """PTM-FIN-23 — a RISK_HOLD row (verified) is final.
    Rules: finalize_from_gateway R3 [BUG-026 setup]."""
    t = mk_txn(db, w2, u2, status="RISK_HOLD", outcome_verified=True, val_id="VAL-ORIG")
    tid = t.id
    ret = fin(db)
    assert ret is t
    gw.validate.assert_not_called()
    r = reread(db, tid)
    assert r.status == "RISK_HOLD"
    assert r.val_id == "VAL-ORIG"
    assert r.outcome_verified is True
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already RISK_HOLD"),
    ]


def test_ptm_fin_24__redirect_success_descriptions(db, w2, t2, gw):
    """PTM-FIN-24 — redirect_success: received + validated_success descriptions.
    Rules: finalize_from_gateway R4."""
    tid = t2.id
    ret = fin(db, source="redirect_success")
    assert ret is t2
    gw.validate.assert_called_once_with("VAL-1")
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    evs = events(db, tid)
    assert len(evs) == 2
    assert evs[0].description == "Callback received via redirect_success"
    assert ev_tuples(evs[1:]) == [
        E(tid, w2.id, "validated_success", "Validated successfully via redirect_success callback"),
    ]


def test_ptm_fin_25__redirect_fail_descriptions(db, w2, t2, gw):
    """PTM-FIN-25 — redirect_fail: received + validated_failed descriptions.
    Rules: finalize_from_gateway R4."""
    tid = t2.id
    gw.validate.return_value = ok(status="FAILED")
    ret = fin(db, source="redirect_fail")
    assert ret is t2
    assert reread(db, tid).status == "VALIDATED_FAILED"
    evs = events(db, tid)
    assert len(evs) == 2
    assert evs[0].description == "Callback received via redirect_fail"
    assert ev_tuples(evs[1:]) == [
        E(tid, w2.id, "validated_failed", "Gateway validation via redirect_fail callback returned status=FAILED"),
    ]


def test_ptm_fin_26__foreign_val_id_not_applied(db, w2, t2, gw):
    """PTM-FIN-26 — a val_id of another tran_id never copies fields or succeeds.
    Rules: finalize_from_gateway R4, _apply R1."""
    tid = t2.id
    gw.validate.return_value = ok(tran_id=B26)
    ret = fin(db)
    assert ret is t2
    gw.validate.assert_called_once_with("VAL-1")
    r = reread(db, tid)
    assert gw_fields(r) == NONE_FIELDS
    assert r.status not in {"VALIDATED_SUCCESS", "RISK_HOLD"}
    evs = events(db, tid)
    assert len(evs) == 2
    assert ev_tuples(evs[:1]) == [E(tid, w2.id, "ipn_received", "Callback received via ipn")]
    assert evs[1].description == f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"


def test_ptm_fin_27__verified_cancel_final(db, t2, gw):
    """PTM-FIN-27 — after a gateway-verified CANCELLED answer the next callback is a duplicate.
    Rules: finalize_from_gateway R3, R5."""
    tid = t2.id
    gw.validate.return_value = ok(status="CANCELLED")
    fin(db)
    s1 = reread(db, tid).status
    n_setup = len(events(db, tid))
    gw.validate.return_value = ok(val_id="VAL-2")
    ret = fin(db, val_id="VAL-2")
    assert ret is t2
    assert gw.validate.call_count == 1
    r = reread(db, tid)
    assert r.status == s1
    assert r.val_id == "VAL-1"
    added = events(db, tid)[n_setup:]
    assert len(added) == 1
    assert added[0].event_type == "duplicate_ignored"
    assert added[0].description.startswith("Duplicate ipn callback ignored; transaction already ")


# =========================================================================== #
# mark_terminal_without_validation  (T is in W2)
# =========================================================================== #

@xbug(BUG028)
def test_ptm_mtw_01__cancel_event_type(db, t2, gw):
    """PTM-MTW-01 — the cancel redirect event is typed `redirect_cancel`.
    Rules: mark_terminal_without_validation R3b [BUG-028]."""
    tid = t2.id
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t2
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "redirect_cancel"
    assert_no_gateway_calls(gw)


@xbug(BUG028)
def test_ptm_mtw_02__success_no_val_id_event_type(db, t2, gw):
    """PTM-MTW-02 — a success redirect without val_id is typed `redirect_success`.
    Rules: mark_terminal_without_validation R3b [BUG-028]."""
    tid = t2.id
    ret = mtw(db, "VALIDATED_FAILED", "redirect_success_no_val_id")
    assert ret is t2
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "redirect_success"
    assert_no_gateway_calls(gw)


@xbug(BUG028)
def test_ptm_mtw_03__fail_no_val_id_event_type(db, t2, gw):
    """PTM-MTW-03 — a fail redirect without val_id is typed `redirect_fail`.
    Rules: mark_terminal_without_validation R3b [BUG-028]."""
    tid = t2.id
    ret = mtw(db, "VALIDATED_FAILED", "redirect_fail_no_val_id")
    assert ret is t2
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].event_type == "redirect_fail"
    assert_no_gateway_calls(gw)


def test_ptm_mtw_04__unknown_tran_id_404(db, t2, gw):
    """PTM-MTW-04 — an unknown tran_id raises 404 and writes nothing.
    Rules: mark_terminal_without_validation R1; Errors row 1."""
    tid = t2.id
    with pytest.raises(HTTPException) as exc:
        mtw(db, "CANCELLED", "redirect_cancel", tran_id="z" * 26)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Unknown tran_id: {'z' * 26}"
    assert n_events(db) == 0
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert_no_gateway_calls(gw)


def test_ptm_mtw_05__lookup_locks_row(db, engine, t2, gw):
    """PTM-MTW-05 — the lookup is SELECT ... FOR UPDATE.
    Rules: mark_terminal_without_validation R1."""
    with SqlCapture(engine) as cap:
        ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t2
    assert cap.has_select_for_update_on_txns()
    assert_no_gateway_calls(gw)


def test_ptm_mtw_06__duplicate_on_success(db, w2, u2, gw):
    """PTM-MTW-06 — a redirect for a VALIDATED_SUCCESS row is a duplicate.
    Rules: mark_terminal_without_validation R2."""
    t = mk_txn(db, w2, u2, status="VALIDATED_SUCCESS", validated_at=V0)
    tid = t.id
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t
    r = reread(db, tid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.validated_at == V0
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored",
          "Duplicate redirect_cancel callback ignored; transaction already VALIDATED_SUCCESS"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_mtw_07__duplicate_on_unverified_cancel(db, w2, t2, gw):
    """PTM-MTW-07 — a second unverified redirect is a duplicate.
    Rules: mark_terminal_without_validation R2."""
    tid = t2.id
    mtw(db, "CANCELLED", "redirect_cancel")
    n_setup = len(events(db, tid))
    ret = mtw(db, "VALIDATED_FAILED", "redirect_fail_no_val_id")
    assert ret is t2
    assert reread(db, tid).status == "CANCELLED"
    assert ev_tuples(events(db, tid)[n_setup:]) == [
        E(tid, w2.id, "duplicate_ignored",
          "Duplicate redirect_fail_no_val_id callback ignored; transaction already CANCELLED"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_mtw_08__duplicate_on_expired(db, w2, u2, gw):
    """PTM-MTW-08 — a redirect for an EXPIRED row is a duplicate.
    Rules: mark_terminal_without_validation R2."""
    t = mk_txn(db, w2, u2, status="EXPIRED", validated_at=V0)
    tid = t.id
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t
    r = reread(db, tid)
    assert r.status == "EXPIRED"
    assert r.validated_at == V0
    assert ev_tuples(events(db, tid)) == [
        E(tid, w2.id, "duplicate_ignored", "Duplicate redirect_cancel callback ignored; transaction already EXPIRED"),
    ]
    assert_no_gateway_calls(gw)


def test_ptm_mtw_09__any_status_string(db, t2, gw):
    """PTM-MTW-09 — terminal_status is not validated.
    Rules: mark_terminal_without_validation R4."""
    tid = t2.id
    ret = mtw(db, "WHATEVER", "redirect_cancel")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "WHATEVER"
    assert r.validated_at == NOW
    assert len(events(db, tid)) == 1
    assert_no_gateway_calls(gw)


def test_ptm_mtw_10__status_20_chars(db, t2, gw):
    """PTM-MTW-10 — a 20-char status is stored.
    Rules: mark_terminal_without_validation R4."""
    tid = t2.id
    ret = mtw(db, "ABCDEFGHIJKLMNOPQRST", "redirect_cancel")
    assert ret is t2
    assert reread(db, tid).status == "ABCDEFGHIJKLMNOPQRST"
    assert_no_gateway_calls(gw)


def test_ptm_mtw_11__status_21_chars_data_error(db, t2, gw):
    """PTM-MTW-11 — a 21-char status raises DataError and changes nothing.
    Rules: mark_terminal_without_validation R4; Errors row 2."""
    tid = t2.id
    with pytest.raises(DataError):
        with db.begin_nested():
            mtw(db, "ABCDEFGHIJKLMNOPQRSTU", "redirect_cancel")
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert len(events(db, tid)) == 0
    assert_no_gateway_calls(gw)


def test_ptm_mtw_12__cancel_applied(db, w2, t2, gw):
    """PTM-MTW-12 — a cancel redirect sets CANCELLED without touching gateway fields.
    Rules: mark_terminal_without_validation R3."""
    tid = t2.id
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "CANCELLED"
    assert r.validated_at == NOW
    assert gw_fields(r) == NONE_FIELDS
    evs = events(db, tid)
    assert len(evs) == 1
    e = evs[0]
    assert e.description == "Marked CANCELLED via redirect_cancel (no val_id to validate)"
    assert e.workspace_id == w2.id
    assert e.performed_by is None
    assert e.metadata_json is None
    assert_no_gateway_calls(gw)


def test_ptm_mtw_13__success_without_val_id(db, t2, gw):
    """PTM-MTW-13 — a success redirect without val_id sets VALIDATED_FAILED.
    Rules: mark_terminal_without_validation R3."""
    tid = t2.id
    ret = mtw(db, "VALIDATED_FAILED", "redirect_success_no_val_id")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert r.val_id is None
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == "Marked VALIDATED_FAILED via redirect_success_no_val_id (no val_id to validate)"
    assert_no_gateway_calls(gw)


def test_ptm_mtw_14__fail_without_val_id(db, t2, gw):
    """PTM-MTW-14 — a fail redirect without val_id sets VALIDATED_FAILED.
    Rules: mark_terminal_without_validation R3."""
    tid = t2.id
    ret = mtw(db, "VALIDATED_FAILED", "redirect_fail_no_val_id")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    evs = events(db, tid)
    assert len(evs) == 1
    assert evs[0].description == "Marked VALIDATED_FAILED via redirect_fail_no_val_id (no val_id to validate)"
    assert_no_gateway_calls(gw)


@xbug(BUG026)
def test_ptm_mtw_15__redirect_outcome_unverified(db, t2, gw):
    """PTM-MTW-15 — a redirect outcome keeps outcome_verified False.
    Rules: mark_terminal_without_validation R3a [BUG-026]."""
    tid = t2.id
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    assert ret is t2
    r = reread(db, tid)
    assert r.status == "CANCELLED"
    assert r.outcome_verified is False
    assert_no_gateway_calls(gw)


# =========================================================================== #
# resolve_risk
# =========================================================================== #

@pytest.fixture
def h(db, w1, u1, clock):
    """Convention "H": T in W1 brought to RISK_HOLD (utcnow = V0 during setup)."""
    return make_h(db, w1, u1, clock)


RESOLUTION_FIELDS = ("risk_resolved_by", "risk_resolved_at", "risk_resolution_note")


def test_ptm_rr_01__approve(db, w1, u1, h):
    """PTM-RR-01 — approving a hold gives VALIDATED_SUCCESS with resolution fields.
    Rules: resolve_risk R3, R4, R5."""
    hid = h.id
    n_setup = len(events(db, hid))
    ret = rr(db, hid, w1.id, u1.id, True, "Customer verified by phone")
    assert ret is h
    r = reread(db, hid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.risk_resolved_by == u1.id
    assert r.risk_resolved_at == NOW
    assert r.risk_resolution_note == "Customer verified by phone"
    assert r.validated_at == V0
    assert r.val_id == "VAL-1"
    assert r.risk_level == 1
    assert r.risk_title == "Suspicious card"
    assert r.bank_tran_id == "BANK-1"
    assert r.card_type == "VISA-Brac bank"
    assert r.verify_sign == "SIG-1"
    assert ev_tuples(events(db, hid)[n_setup:]) == [
        E(hid, w1.id, "risk_resolved", "Risk hold approved: Customer verified by phone", performed_by=u1.id),
    ]


def test_ptm_rr_02__reject(db, w1, u1, h):
    """PTM-RR-02 — rejecting a hold gives VALIDATED_FAILED with resolution fields.
    Rules: resolve_risk R3, R4, R5."""
    hid = h.id
    n_setup = len(events(db, hid))
    ret = rr(db, hid, w1.id, u1.id, False, "Card reported stolen")
    assert ret is h
    r = reread(db, hid)
    assert r.status == "VALIDATED_FAILED"
    assert r.risk_resolved_by == u1.id
    assert r.risk_resolved_at == NOW
    assert r.risk_resolution_note == "Card reported stolen"
    assert r.validated_at == V0
    assert r.val_id == "VAL-1"
    assert ev_tuples(events(db, hid)[n_setup:]) == [
        E(hid, w1.id, "risk_resolved", "Risk hold rejected: Card reported stolen", performed_by=u1.id),
    ]


def test_ptm_rr_03__empty_note(db, w1, u1, h):
    """PTM-RR-03 — an empty note is stored and ends the description.
    Rules: resolve_risk R4, R5."""
    hid = h.id
    n_setup = len(events(db, hid))
    ret = rr(db, hid, w1.id, u1.id, True, "")
    assert ret is h
    r = reread(db, hid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.risk_resolution_note == ""
    added = events(db, hid)[n_setup:]
    assert len(added) == 1
    assert added[0].description == "Risk hold approved: "


def test_ptm_rr_04__not_found_404(db, w1, u1, h):
    """PTM-RR-04 — an unknown transaction id raises 404.
    Rules: resolve_risk R1; Errors row 1."""
    hid = h.id
    n_setup = len(events(db, hid))
    with pytest.raises(HTTPException) as exc:
        rr(db, 999999, w1.id, u1.id, True, "x")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Payment transaction 999999 not found"
    r = reread(db, hid)
    assert r.status == "RISK_HOLD"
    assert tuple(getattr(r, f) for f in RESOLUTION_FIELDS) == (None, None, None)
    assert len(events(db, hid)) == n_setup


def test_ptm_rr_05__other_workspace_404(db, w1, w2, u1, u2, clock):
    """PTM-RR-05 — a hold in another workspace is not found.
    Rules: resolve_risk R1; Errors row 1."""
    h = make_h(db, w2, u2, clock)
    hid = h.id
    n_setup = len(events(db, hid))
    with pytest.raises(HTTPException) as exc:
        rr(db, hid, w1.id, u1.id, True, "x")
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Payment transaction {hid} not found"
    r = reread(db, hid)
    assert r.status == "RISK_HOLD"
    assert r.risk_resolved_by is None
    assert r.risk_resolved_at is None
    assert r.risk_resolution_note is None
    assert len(events(db, hid)) == n_setup


def test_ptm_rr_06__not_on_hold_400(db, w1, u1, t):
    """PTM-RR-06 — resolving a non-RISK_HOLD transaction raises 400.
    Rules: resolve_risk R2; Errors row 2."""
    tid = t.id
    with pytest.raises(HTTPException) as exc:
        rr(db, tid, w1.id, u1.id, True, "x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only transactions in RISK_HOLD can be resolved (current status: INITIATED)"
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert tuple(getattr(r, f) for f in RESOLUTION_FIELDS) == (None, None, None)
    assert len(events(db, tid)) == 0


def test_ptm_rr_07__second_resolve_400(db, w1, u1, h):
    """PTM-RR-07 — a second resolve of the same hold raises 400.
    Rules: resolve_risk R6, R2."""
    hid = h.id
    rr(db, hid, w1.id, u1.id, True, "First")
    with pytest.raises(HTTPException) as exc:
        rr(db, hid, w1.id, u1.id, False, "Second")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only transactions in RISK_HOLD can be resolved (current status: VALIDATED_SUCCESS)"
    r = reread(db, hid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.risk_resolution_note == "First"
    assert ev_types(events(db, hid)).count("risk_resolved") == 1


@xbug(BUG029)
def test_ptm_rr_08__lookup_locks_row(db, engine, w1, u1, h):
    """PTM-RR-08 — the resolve lookup is SELECT ... FOR UPDATE.
    Rules: resolve_risk R6a [BUG-029]."""
    hid = h.id
    with SqlCapture(engine) as cap:
        ret = rr(db, hid, w1.id, u1.id, True, "x")
    assert ret is h
    assert cap.has_select_for_update_on_txns()
    assert reread(db, hid).status == "VALIDATED_SUCCESS"


@xbug(BUG026)
def test_ptm_rr_09__reject_keeps_verified(db, w1, u1):
    """PTM-RR-09 — rejecting keeps outcome_verified True.
    Rules: resolve_risk R3a [BUG-026]; _apply R12."""
    hs = make_h_star(db, w1, u1)
    hid = hs.id
    ret = rr(db, hid, w1.id, u1.id, False, "Fraud")
    assert ret is hs
    r = reread(db, hid)
    assert r.status == "VALIDATED_FAILED"
    assert r.outcome_verified is True


@xbug(BUG026)
def test_ptm_rr_10__approve_keeps_verified(db, w1, u1):
    """PTM-RR-10 — approving keeps outcome_verified True.
    Rules: resolve_risk R3a [BUG-026]."""
    hs = make_h_star(db, w1, u1)
    hid = hs.id
    ret = rr(db, hid, w1.id, u1.id, True, "Customer verified by phone")
    assert ret is hs
    r = reread(db, hid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.outcome_verified is True


@xbug(BUG026)
def test_ptm_rr_11__rejected_not_revalidated(db, w2, u2, gw):
    """PTM-RR-11 — a rejected hold is final; a later callback is a duplicate.
    Rules: resolve_risk R3a [BUG-026]; finalize_from_gateway R3, R3a."""
    hs = make_h_star(db, w2, u2)
    hid = hs.id
    rr(db, hid, w2.id, u2.id, False, "Fraud")
    n_setup = len(events(db, hid))
    gw.validate.return_value = ok(val_id="VAL-NEW")
    ret = fin(db, val_id="VAL-NEW")
    assert ret is hs
    gw.validate.assert_not_called()
    r = reread(db, hid)
    assert r.status == "VALIDATED_FAILED"
    assert r.outcome_verified is True
    assert r.val_id == "VAL-1"
    assert r.risk_resolution_note == "Fraud"
    assert ev_tuples(events(db, hid)[n_setup:]) == [
        E(hid, w2.id, "duplicate_ignored", "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"),
    ]


# =========================================================================== #
# reconcile_stuck_transactions
# =========================================================================== #

def cand(db, ws, user, tran_id, initiated_at, **kw):
    """Candidate row: an INITIATED transaction like T with the given initiated_at."""
    return mk_txn(db, ws, user, tran_id=tran_id, initiated_at=initiated_at, **kw)


def q_valid(tran_id, **kw):
    fields = dict(status="VALID", tran_id=tran_id, val_id="VAL-9", amount=Decimal("500.00"),
                  currency="BDT", risk_level=0)
    fields.update(kw)
    return ValidationResult(**fields)


def queried(gw):
    return [c.args[0] for c in gw.query_by_tran_id.call_args_list]


def test_ptm_rec_01__cutoff_strict(db, w1, u1, gw):
    """PTM-REC-01 — only rows strictly older than the cutoff are swept.
    Rules: reconcile_stuck_transactions R1, R6."""
    a = cand(db, w1, u1, A26, NOW - timedelta(minutes=30, seconds=1))
    b = cand(db, w1, u1, B26, NOW - timedelta(minutes=30))
    c = cand(db, w1, u1, C26, NOW - timedelta(minutes=29))
    aid, bid, cid = a.id, b.id, c.id
    res = rec(db)
    assert ids(res) == [aid]
    assert queried(gw) == [A26]
    assert reread(db, aid).status == "EXPIRED"
    for x in (bid, cid):
        r = reread(db, x)
        assert r.status == "INITIATED"
        assert r.validated_at is None
        assert len(events(db, x)) == 0


def test_ptm_rec_02__non_initiated_ignored(db, w1, u1, gw):
    """PTM-REC-02 — rows not INITIATED are never swept.
    Rules: reconcile_stuck_transactions R1, R7."""
    old = NOW - timedelta(hours=2)
    statuses = ["EXPIRED", "VALIDATED_SUCCESS", "CANCELLED", "VALIDATED_FAILED", "INIT_FAILED"]
    rows = [cand(db, w1, u1, str(i + 1) * 26, old, status=s) for i, s in enumerate(statuses)]
    t = cand(db, w1, u1, A26, old)
    to_risk_hold(db, t)
    expected = {r.id: s for r, s in zip(rows, statuses)}
    expected[t.id] = "RISK_HOLD"
    before = n_events(db)
    res = rec(db)
    assert res == []
    gw.query_by_tran_id.assert_not_called()
    for rid, s in expected.items():
        assert reread(db, rid).status == s
    assert n_events(db) == before


def test_ptm_rec_03__all_workspaces(db, w1, w2, u1, u2):
    """PTM-REC-03 — the sweep covers every workspace; events keep the row's workspace.
    Rules: reconcile_stuck_transactions R1, R10."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    b = cand(db, w2, u2, B26, NOW - timedelta(hours=1))
    aid, bid = a.id, b.id
    res = rec(db)
    assert ids(res) == [aid, bid]
    assert reread(db, aid).status == "EXPIRED"
    assert reread(db, bid).status == "EXPIRED"
    a_exp = [e for e in events(db, aid) if e.event_type == "expired"]
    b_exp = [e for e in events(db, bid) if e.event_type == "expired"]
    assert a_exp[0].workspace_id == w1.id
    assert b_exp[0].workspace_id == w2.id


def _xyz(db, w1, u1):
    x = cand(db, w1, u1, "7" * 26, NOW - timedelta(hours=1))
    y = cand(db, w1, u1, "8" * 26, NOW - timedelta(hours=3))
    z = cand(db, w1, u1, "9" * 26, NOW - timedelta(hours=2))
    return x.id, y.id, z.id


def test_ptm_rec_04__oldest_first_limit(db, w1, u1, gw):
    """PTM-REC-04 — oldest first, limited to `limit`.
    Rules: reconcile_stuck_transactions R2."""
    xid, yid, zid = _xyz(db, w1, u1)
    res = rec(db, limit=2)
    assert ids(res) == [yid, zid]
    assert queried(gw) == ["8" * 26, "9" * 26]
    assert reread(db, xid).status == "INITIATED"
    assert len(events(db, xid)) == 0


def test_ptm_rec_05__limit_covers_all(db, w1, u1):
    """PTM-REC-05 — with limit 3 all three are swept, oldest first.
    Rules: reconcile_stuck_transactions R2."""
    xid, yid, zid = _xyz(db, w1, u1)
    res = rec(db, limit=3)
    assert ids(res) == [yid, zid, xid]
    for rid in (xid, yid, zid):
        assert reread(db, rid).status == "EXPIRED"


def test_ptm_rec_06__default_limit_200(db, w1, u1, gw):
    """PTM-REC-06 — the default limit is 200; the newest of 201 is left.
    Rules: reconcile_stuck_transactions R2."""
    rows = []
    for i in range(201):
        row = PaymentTransaction(
            workspace_id=w1.id, tran_id=f"{i:026x}", status="INITIATED", amount=Decimal("500.00"),
            currency="BDT", cus_phone="01711000000", initiated_by=u1.id,
            initiated_at=NOW - timedelta(hours=2, seconds=i), updated_at=UPD0,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    row0_id = rows[0].id
    res = rec(db)
    assert len(res) == 200
    assert row0_id not in ids(res)
    assert reread(db, row0_id).status == "INITIATED"
    assert len(events(db, row0_id)) == 0
    assert gw.query_by_tran_id.call_count == 200


def test_ptm_rec_07__resolved_meanwhile_skipped(db, w1, u1, gw):
    """PTM-REC-07 — a candidate resolved after selection is skipped.
    Rules: reconcile_stuck_transactions R3."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    aid, bid = a.id, b.id

    # Race simulation (Conventions): while handling A, a live callback resolves B.
    def side_effect(tran_id, *args, **kwargs):
        if tran_id == A26:
            other = db.get(PaymentTransaction, bid)
            other.status = "VALIDATED_SUCCESS"
            db.flush()
        return unattempted(tran_id)

    gw.query_by_tran_id.side_effect = side_effect
    res = rec(db)
    assert ids(res) == [aid]
    assert queried(gw) == [A26]
    assert reread(db, bid).status == "VALIDATED_SUCCESS"
    assert len(events(db, bid)) == 0


def test_ptm_rec_08__relock_for_update(db, engine, w1, u1):
    """PTM-REC-08 — each candidate is re-read with SELECT ... FOR UPDATE.
    Rules: reconcile_stuck_transactions R3."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    with SqlCapture(engine) as cap:
        res = rec(db)
    assert ids(res) == [aid]
    assert cap.has_select_for_update_on_txns()


@xbug(BUG031)
def test_ptm_rec_09__query_by_tran_id_alone(db, w1, u1, gw):
    """PTM-REC-09 — the gateway is queried with the tran_id only.
    Rules: reconcile_stuck_transactions R4a [BUG-031]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = None
    gw.query_by_tran_id.return_value = q_valid(A26)
    res = rec(db)
    assert ids(res) == [aid]
    assert gw.query_by_tran_id.call_count == 1
    assert gw.query_by_tran_id.call_args == call(A26)


def test_ptm_rec_10__validated_status_success(db, w1, u1, gw):
    """PTM-REC-10 — a VALIDATED answer finalizes the row as success.
    Rules: reconcile_stuck_transactions R5."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: q_valid(A26, status="VALIDATED")})
    res = rec(db)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "VALIDATED_SUCCESS"
    assert ev_types(events(db, aid)) == ["validated_success"]


def test_ptm_rec_11__amount_mismatch(db, w1, u1, gw):
    """PTM-REC-11 — a VALID answer with the wrong amount fails the row.
    Rules: reconcile_stuck_transactions R5."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="VALID", tran_id=A26, amount=Decimal("499.99"), currency="BDT")})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "validated_failed", "Amount mismatch: expected 500.00 BDT, gateway reported 499.99 BDT"),
    ]


def test_ptm_rec_12__risk_hold(db, w1, u1, gw):
    """PTM-REC-12 — a risky VALID answer puts the row on hold.
    Rules: reconcile_stuck_transactions R5."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="VALID", tran_id=A26, amount=Decimal("500.00"), currency="BDT",
        risk_level=1, risk_title="Suspicious card")})
    res = rec(db)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "RISK_HOLD"
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "risk_hold",
          "Validated via reconciliation but flagged high-risk (Suspicious card) — held for review"),
    ]


@xbug(BUG030)
def test_ptm_rec_13__gateway_failed(db, w1, u1, gw):
    """PTM-REC-13 — a gateway FAILED answer gives VALIDATED_FAILED, not EXPIRED.
    Rules: reconcile_stuck_transactions R5a [BUG-030]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="FAILED", tran_id=A26, val_id="VAL-9", amount=Decimal("500.00"), currency="BDT")})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "VALIDATED_FAILED"
    assert r.validated_at == NOW
    assert r.val_id == "VAL-9"
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "validated_failed", "Gateway validation via reconciliation returned status=FAILED"),
    ]


@xbug(BUG030, BUG025)
def test_ptm_rec_14__gateway_cancelled(db, w1, u1, gw):
    """PTM-REC-14 — a gateway CANCELLED answer gives CANCELLED, not EXPIRED.
    Rules: reconcile_stuck_transactions R5a [BUG-030] (needs BUG-025 too)."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(status="CANCELLED", tran_id=A26)})
    res = rec(db)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "CANCELLED"
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "validated_cancelled", "Gateway validation via reconciliation returned status=CANCELLED"),
    ]


@xbug(BUG023)
def test_ptm_rec_15__foreign_tran_id_rejected(db, w1, u1, gw):
    """PTM-REC-15 — a sweep answer for another tran_id leaves the row INITIATED.
    Rules: reconcile_stuck_transactions R5b [BUG-023]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="VALID", tran_id="f" * 26, amount=Decimal("500.00"), currency="BDT")})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    evs = events(db, aid)
    assert len(evs) == 1
    assert evs[0].event_type == "validation_rejected"


def test_ptm_rec_16__unattempted_expires(db, w1, u1, gw):
    """PTM-REC-16 — an UNATTEMPTED answer expires the row without copying fields.
    Rules: reconcile_stuck_transactions R6."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="UNATTEMPTED", tran_id=A26, val_id="VAL-X", bank_tran_id="BANK-X")})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "EXPIRED"
    assert r.validated_at == NOW
    assert r.val_id is None
    assert r.bank_tran_id is None
    assert r.risk_level is None
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "expired", "No resolution found after 30 minutes (gateway status: UNATTEMPTED)"),
    ]


def test_ptm_rec_17__custom_minutes_in_description(db, w1, u1, gw):
    """PTM-REC-17 — the configured minutes and gateway status appear in the description.
    Rules: reconcile_stuck_transactions R6."""
    a = cand(db, w1, u1, A26, NOW - timedelta(minutes=46))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(status="INVALID_TRANSACTION", tran_id=A26)})
    res = rec(db, older_than_minutes=45)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "EXPIRED"
    assert events(db, aid)[0].description == (
        "No resolution found after 45 minutes (gateway status: INVALID_TRANSACTION)")


def test_ptm_rec_18__empty_status(db, w1, u1, gw):
    """PTM-REC-18 — an empty gateway status expires the row.
    Rules: reconcile_stuck_transactions R6."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(status="", tran_id=A26)})
    res = rec(db)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "EXPIRED"
    assert events(db, aid)[0].description == "No resolution found after 30 minutes (gateway status: )"


@xbug(BUG027)
def test_ptm_rec_19__late_ipn_replaces_expired(db, w1, u1, gw):
    """PTM-REC-19 — a verified IPN after the sweep replaces EXPIRED.
    Rules: reconcile_stuck_transactions R6, finalize_from_gateway R3b [BUG-027]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    res = rec(db)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "EXPIRED"
    ret = fin(db, tran_id=A26, val_id="VAL-1", source="ipn")
    assert ret is a
    r = reread(db, aid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-1"
    assert ev_types(events(db, aid))[-2:] == ["ipn_received", "validated_success"]


def test_ptm_rec_20__mixed_batch(db, w1, u1, gw):
    """PTM-REC-20 — each candidate is handled once with its own outcome.
    Rules: reconcile_stuck_transactions R7."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    c = cand(db, w1, u1, C26, NOW - timedelta(hours=1))
    aid, bid, cid = a.id, b.id, c.id
    gw.query_by_tran_id.side_effect = query_map({
        A26: ValidationResult(status="VALID", tran_id=A26, amount=Decimal("500.00"), currency="BDT", risk_level=0),
        C26: ValidationResult(status="VALID", tran_id=C26, amount=Decimal("1"), currency="BDT"),
    })
    res = rec(db)
    assert ids(res) == [aid, bid, cid]
    assert [reread(db, x).status for x in (aid, bid, cid)] == ["VALIDATED_SUCCESS", "EXPIRED", "VALIDATED_FAILED"]
    for x in (aid, bid, cid):
        assert len(events(db, x)) == 1


@xbug(BUG032)
def test_ptm_rec_21__middle_error_skipped(db, w1, u1, gw):
    """PTM-REC-21 — a gateway error on one candidate is logged and the sweep continues.
    Rules: reconcile_stuck_transactions R8 [BUG-032]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    c = cand(db, w1, u1, C26, NOW - timedelta(hours=1))
    aid, bid, cid = a.id, b.id, c.id
    gw.query_by_tran_id.side_effect = query_map({B26: RuntimeError("gateway timeout")})
    res = rec(db)
    assert ids(res) == [aid, cid]
    assert reread(db, aid).status == "EXPIRED"
    assert reread(db, cid).status == "EXPIRED"
    r = reread(db, bid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert gw_fields(r) == NONE_FIELDS
    assert ev_tuples(events(db, bid)) == [
        E(bid, w1.id, "reconciliation_error", "Gateway query failed during reconciliation: gateway timeout"),
    ]
    assert gw.query_by_tran_id.call_count == 3


@xbug(BUG032)
def test_ptm_rec_22__first_error_skipped(db, w1, u1, gw):
    """PTM-REC-22 — an error on the first candidate does not stop the others.
    Rules: reconcile_stuck_transactions R8 [BUG-032]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    c = cand(db, w1, u1, C26, NOW - timedelta(hours=1))
    aid, bid, cid = a.id, b.id, c.id
    gw.query_by_tran_id.side_effect = query_map({A26: RuntimeError("bad response")})
    res = rec(db)
    assert ids(res) == [bid, cid]
    assert reread(db, bid).status == "EXPIRED"
    assert reread(db, cid).status == "EXPIRED"
    assert reread(db, aid).status == "INITIATED"
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "reconciliation_error", "Gateway query failed during reconciliation: bad response"),
    ]


def test_ptm_rec_23__zero_minutes(db, w1, u1):
    """PTM-REC-23 — older_than_minutes=0 sweeps rows strictly before now.
    Rules: reconcile_stuck_transactions R9."""
    a = cand(db, w1, u1, A26, NOW - timedelta(seconds=1))
    b = cand(db, w1, u1, B26, NOW)
    aid, bid = a.id, b.id
    res = rec(db, older_than_minutes=0)
    assert ids(res) == [aid]
    assert reread(db, bid).status == "INITIATED"
    assert len(events(db, bid)) == 0


def test_ptm_rec_24__negative_minutes(db, w1, u1):
    """PTM-REC-24 — a negative window moves the cutoff into the future.
    Rules: reconcile_stuck_transactions R9."""
    a = cand(db, w1, u1, A26, NOW)
    aid = a.id
    res = rec(db, older_than_minutes=-10)
    assert ids(res) == [aid]
    assert reread(db, aid).status == "EXPIRED"
    assert events(db, aid)[0].description == "No resolution found after -10 minutes (gateway status: UNATTEMPTED)"


def test_ptm_rec_25__valid_answer_success(db, w1, u1, gw):
    """PTM-REC-25 — a VALID sweep answer finalizes the row as success.
    Rules: reconcile_stuck_transactions R4, R5."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2), val_id=None)
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: q_valid(A26)})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "VALIDATED_SUCCESS"
    assert r.val_id == "VAL-9"
    assert r.validated_at == NOW
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "validated_success", "Validated successfully via reconciliation"),
    ]
    assert gw.query_by_tran_id.call_count == 1
    assert gw.query_by_tran_id.call_args.args[0] == A26


def test_ptm_rec_26__foreign_tran_id_not_applied(db, w1, u1, gw):
    """PTM-REC-26 — a sweep answer for another tran_id never copies fields or succeeds.
    Rules: reconcile_stuck_transactions R5."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    gw.query_by_tran_id.side_effect = query_map({A26: ValidationResult(
        status="VALID", tran_id="f" * 26, val_id="VAL-F", amount=Decimal("500.00"), currency="BDT")})
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.val_id is None
    assert r.bank_tran_id is None
    assert r.status not in {"VALIDATED_SUCCESS", "RISK_HOLD"}
    evs = events(db, aid)
    assert len(evs) == 1
    assert evs[0].description == f"val_id/tran_id mismatch via reconciliation: gateway resolved it to tran_id={'f' * 26}"


@xbug(BUG026)
def test_ptm_rec_27__expired_unverified(db, w1, u1):
    """PTM-REC-27 — the sweep's EXPIRED leaves outcome_verified False.
    Rules: reconcile_stuck_transactions R6, _apply R12 [BUG-026]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=2))
    aid = a.id
    res = rec(db)
    assert ids(res) == [aid]
    r = reread(db, aid)
    assert r.status == "EXPIRED"
    assert r.outcome_verified is False


@xbug(BUG032)
def test_ptm_rec_28__empty_message_uses_class_name(db, w1, u1, gw):
    """PTM-REC-28 — an exception with no message is logged by class name.
    Rules: reconcile_stuck_transactions R8 [BUG-032]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    aid, bid = a.id, b.id
    gw.query_by_tran_id.side_effect = query_map({A26: TimeoutError()})
    res = rec(db)
    assert ids(res) == [bid]
    assert reread(db, bid).status == "EXPIRED"
    assert reread(db, aid).status == "INITIATED"
    assert ev_tuples(events(db, aid)) == [
        E(aid, w1.id, "reconciliation_error", "Gateway query failed during reconciliation: TimeoutError"),
    ]


@xbug(BUG032)
def test_ptm_rec_29__db_error_on_candidate_undone(db, w1, u1, gw):
    """PTM-REC-29 — a DataError on one candidate's update is undone and logged; others complete.
    Rules: reconcile_stuck_transactions R8 [BUG-032]."""
    a = cand(db, w1, u1, A26, NOW - timedelta(hours=3))
    b = cand(db, w1, u1, B26, NOW - timedelta(hours=2))
    c = cand(db, w1, u1, C26, NOW - timedelta(hours=1))
    aid, bid, cid = a.id, b.id, c.id
    gw.query_by_tran_id.side_effect = query_map({B26: ValidationResult(
        status="VALID", tran_id=B26, val_id="VAL-B", amount=Decimal("500.00"), currency="BDT",
        risk_level=0, risk_title="R" * 51, bank_tran_id="BANK-B")})
    res = rec(db)
    assert ids(res) == [aid, cid]
    assert reread(db, aid).status == "EXPIRED"
    assert reread(db, cid).status == "EXPIRED"
    r = reread(db, bid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert r.val_id is None
    assert r.risk_title is None
    assert r.bank_tran_id is None
    assert r.risk_level is None
    evs = events(db, bid)
    assert len(evs) == 1
    assert evs[0].event_type == "reconciliation_error"
    prefix = "Gateway query failed during reconciliation: "
    assert evs[0].description.startswith(prefix)
    assert len(evs[0].description) > len(prefix)

# --------------------------------------------------------------------------- #
# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
# --------------------------------------------------------------------------- #
def commit_spy(db, monkeypatch):
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# [claude] PTM-LOG-05
def test_ptm_log_05__event_flushed_not_committed(db, w1, u1, monkeypatch):
    """PTM-LOG-05 — the event is flushed but not committed: a rollback removes it.
    Rules: _log_event Side effects (no commit)."""
    t = mk_txn(db, w1, u1)
    tid = t.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    ret = mgr._log_event(db, t, "expired", "x")
    # Then 1
    assert ret is None
    # Then 2
    assert len(events(db, tid)) == 1
    sp.rollback()
    # Then 3
    assert len(events(db, tid)) == 0
    # Then 4
    spy.assert_not_called()


# [claude] PTM-INIT-32
def test_ptm_init_32__start_flushed_not_committed(db, w1, u1, monkeypatch):
    """PTM-INIT-32 — the new txn and event are flushed but not committed: a rollback removes both.
    Rules: initiate_payment Side effects (no commit)."""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    res = initiate(db, w1, u1)
    # Then 1
    assert_returns_reread(db, res, w1.id, "INITIATED")
    # Then 2
    assert n_txns(db, w1.id) == 1
    # Then 3
    assert n_events(db) == 1
    sp.rollback()
    # Then 4
    assert n_txns(db, w1.id) == 0
    # Then 5
    assert n_events(db) == 0
    # Then 6
    spy.assert_not_called()


# [claude] PTM-AVR-44
def test_ptm_avr_44__result_flushed_not_committed(db, t, monkeypatch):
    """PTM-AVR-44 — the applied result is flushed but not committed: a rollback restores the txn.
    Rules: _apply_validation_result Side effects (no commit)."""
    tid = t.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    ret = apply_(db, t, ok())
    # Then 1
    assert ret is t
    # Then 2
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    # Then 3
    assert len(events(db, tid)) == 1
    sp.rollback()
    # Then 4
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert r.val_id is None
    # Then 5
    assert len(events(db, tid)) == 0
    # Then 6
    spy.assert_not_called()


# [claude] PTM-FIN-28
def test_ptm_fin_28__callback_flushed_not_committed(db, t2, monkeypatch):
    """PTM-FIN-28 — a finalized callback is flushed but not committed: a rollback restores the txn.
    Rules: finalize_from_gateway Side effects (no commit)."""
    tid = t2.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    ret = fin(db)
    # Then 1
    assert ret is t2
    # Then 2
    assert reread(db, tid).status == "VALIDATED_SUCCESS"
    # Then 3
    assert len(events(db, tid)) == 2
    sp.rollback()
    # Then 4
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    assert r.val_id is None
    # Then 5
    assert len(events(db, tid)) == 0
    # Then 6
    spy.assert_not_called()


# [claude] PTM-MTW-16
def test_ptm_mtw_16__terminal_flushed_not_committed(db, t2, gw, monkeypatch):
    """PTM-MTW-16 — an unverified outcome is flushed but not committed: a rollback restores the txn.
    Rules: mark_terminal_without_validation Side effects (no commit)."""
    tid = t2.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    ret = mtw(db, "CANCELLED", "redirect_cancel")
    # Then 1
    assert ret is t2
    # Then 2
    assert reread(db, tid).status == "CANCELLED"
    # Then 3
    assert len(events(db, tid)) == 1
    sp.rollback()
    # Then 4
    r = reread(db, tid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    # Then 5
    assert len(events(db, tid)) == 0
    # Then 6
    assert_no_gateway_calls(gw)
    # Then 7
    spy.assert_not_called()


# [claude] PTM-RR-12
def test_ptm_rr_12__resolution_flushed_not_committed(db, w1, u1, h, monkeypatch):
    """PTM-RR-12 — a resolution is flushed but not committed: a rollback restores the hold.
    Rules: resolve_risk Side effects (no commit)."""
    hid = h.id
    n_setup = len(events(db, hid))
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    ret = rr(db, hid, w1.id, u1.id, True, "Customer verified by phone")
    # Then 1
    assert ret is h
    # Then 2
    assert reread(db, hid).status == "VALIDATED_SUCCESS"
    # Then 3
    assert len(events(db, hid)) - n_setup == 1
    sp.rollback()
    # Then 4
    r = reread(db, hid)
    assert r.status == "RISK_HOLD"
    assert r.risk_resolved_by is None
    assert r.risk_resolved_at is None
    assert r.risk_resolution_note is None
    # Then 5
    assert len(events(db, hid)) - n_setup == 0
    # Then 6
    spy.assert_not_called()


# [claude] PTM-REC-30
def test_ptm_rec_30__sweep_flushed_not_committed(db, w1, u1, monkeypatch):
    """PTM-REC-30 — a sweep is flushed but not committed: a rollback restores the candidate.
    Rules: reconcile_stuck_transactions Side effects (no commit)."""
    a = mk_txn(db, w1, u1, initiated_at=NOW - timedelta(hours=2))
    aid = a.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    res = rec(db)
    # Then 1
    assert ids(res) == [aid]
    # Then 2
    assert reread(db, aid).status == "EXPIRED"
    # Then 3
    assert len(events(db, aid)) == 1
    sp.rollback()
    # Then 4
    r = reread(db, aid)
    assert r.status == "INITIATED"
    assert r.validated_at is None
    # Then 5
    assert len(events(db, aid)) == 0
    # Then 6
    spy.assert_not_called()
