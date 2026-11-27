"""Unit tests for app/services/payment_transaction_service.py.

Implements tests/unit/services/payment_transaction_service.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture): a `commit()` only releases a
savepoint, so the service's commits are safe and the fixture's outer rollback discards
everything. Patched in every test (Conventions "Gateway", "Fixed values"):
`app.managers.payment_transaction_manager.get_sslcommerz_client` (returns the mock `gw`) and
`app.managers.payment_transaction_manager.utcnow` (returns NOW). Patched only where a card
says so: `app.managers.payment_transaction_manager.secrets.token_hex` (I-07), the commit /
rollback / refresh wraps of Conventions, and the race simulation of IK-28, IK-29, IK-43
(`PaymentTransactionDAO.get_by_workspace_and_idempotency_key`).

Row names of the cards are the lower-case names here (T -> t, `W1.id` -> `w1.id`);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (naive datetimes per Conventions; Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.payment_transaction import PaymentTransactionDAO
from app.integrations.sslcommerz.client import InitSessionResult, ValidationResult
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_transaction_event import PaymentTransactionEvent
from app.models.profile import Profile
from app.schemas.payment_transaction import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentTransactionDetailResponse,
    PaymentTransactionEventResponse,
    PaymentTransactionResponse,
)
from app.services import payment_transaction_service as pts_module
from app.services.payment_transaction_service import payment_transaction_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc"
svc = payment_transaction_service
# `_to_response` is a module-level function of the service module (cases rev 2a)
_to_response = pts_module._to_response

MISSING = 999999999
NOW = datetime(2026, 9, 27, 12, 0, 0)
A26 = "a" * 26
B26 = "b" * 26
C26 = "c" * 26
Z26 = "f" * 26  # never stored
E26 = "e" * 26  # row X
HEX26 = r"^[0-9a-f]{26}$"
URL1 = "https://sandbox.example/pay/SESS-1"
URL2 = "https://sandbox.example/pay/SESS-2"
NOTE = "Card holder confirmed by phone"
K = "K-1"
IDEM409 = "This idempotency key was already used for a different payment"

# Convention "Gateway"
OKS = InitSessionResult(status="SUCCESS", session_key="SESS-1", gateway_page_url=URL1)
REFUSED = InitSessionResult(status="FAILED", failed_reason="Store is de-active")
SESS2 = InitSessionResult(status="SUCCESS", session_key="SESS-2", gateway_page_url=URL2)


def OKV(t):
    return ValidationResult(
        status="VALID",
        tran_id=t,
        val_id="VAL-1",
        amount=Decimal("500.00"),
        currency="BDT",
        risk_level=0,
        risk_title="Safe",
        bank_tran_id="BANK-1",
        card_type="VISA-Brac bank",
        verify_sign="SIG-1",
    )


def RISKY(t):
    r = OKV(t)
    r.risk_level = 1
    r.risk_title = "Suspicious card"
    return r


# Convention "Requests": REQ / "REQ but X"
def req(**but):
    fields = {"amount": Decimal(500), "currency": "BDT", "cus_phone": "01711000000"}
    fields.update(but)
    return InitiatePaymentRequest(**fields)


# Convention "REQ0" = REQ without currency
def req0():
    return InitiatePaymentRequest(amount=Decimal(500), cus_phone="01711000000")


# Convention "Fingerprint": fp(obj), FPO (REQ sent by U1), FPX = fp(FPO)
def fp(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def fpo(u1):
    return {
        "amount": "500",
        "currency": "BDT",
        "cus_email": None,
        "cus_name": None,
        "cus_phone": "01711000000",
        "profile_id": u1.id,
        "value_a": None,
        "value_b": None,
        "value_c": None,
        "value_d": None,
    }


def fpx(u1):
    return fp(fpo(u1))


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (W0 < W1 < W2; U1 Karim, U2 Rahim, U3 Selina)
# --------------------------------------------------------------------------- #


@pytest.fixture
def w0(db):
    return make_workspace(db)


@pytest.fixture
def w1(db, w0):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db, name="Karim", email="karim@example.com")


@pytest.fixture
def u2(db, u1):
    return make_profile(db, name="Rahim")


@pytest.fixture
def u3(db, u2):
    return make_profile(db, name="Selina")


@pytest.fixture(autouse=True)
def standing(u3):
    pass


# Convention "Gateway" + NOW: patched in every test
@pytest.fixture(autouse=True)
def gw():
    m = MagicMock()
    m.init_session.return_value = OKS
    m.validate.return_value = OKV(A26)
    with (
        patch(
            "app.managers.payment_transaction_manager.get_sslcommerz_client",
            return_value=m,
        ),
        patch("app.managers.payment_transaction_manager.utcnow", return_value=NOW),
    ):
        yield m


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def t_fields(w1, u1, **but):
    fields = {
        "workspace_id": w1.id,
        "tran_id": A26,
        "status": "INITIATED",
        "amount": Decimal("500.00"),
        "currency": "BDT",
        "cus_name": "Karim",
        "cus_email": "karim@example.com",
        "cus_phone": "01711000000",
        "initiated_by": u1.id,
        "session_key": "SESS-0",
        "gateway_page_url": "https://sandbox.example/pay/SESS-0",
    }
    fields.update(but)
    return fields


# Convention "T" (and "T but ..."): one row, flushed
@pytest.fixture
def mk_t(db, w1, u1):
    def _mk(**but):
        row = PaymentTransaction(**t_fields(w1, u1, **but))
        db.add(row)
        db.flush()
        return row

    return _mk


# Convention "X" = T but tran_id "e"*26, flushed, not committed
@pytest.fixture
def mk_x(mk_t):
    def _mk():
        return mk_t(tran_id=E26)

    return _mk


# Convention "ev(T, type, at)"
def ev(db, t, etype, at, **but):
    fields = {
        "workspace_id": t.workspace_id,
        "payment_transaction_id": t.id,
        "event_type": etype,
        "description": f"{etype} note",
        "created_at": at,
    }
    fields.update(but)
    row = PaymentTransactionEvent(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "held(T)"
def held(db, gw, t):
    gw.validate.return_value = RISKY(t.tran_id)
    svc.handle_gateway_callback(db, tran_id=t.tran_id, val_id="VAL-1", source="ipn")


# Convention "paid(T)"
def paid(db, gw, t):
    gw.validate.return_value = OKV(t.tran_id)
    svc.handle_gateway_callback(db, tran_id=t.tran_id, val_id="VAL-1", source="ipn")


# Convention "first(ws, user, req, key)" -> (A, A_ROW)
def first(db, ws, user, request, key):
    a = svc.initiate_payment(
        db, workspace_id=ws, user=user, request=request, idempotency_key=key
    )
    a_row = db.execute(
        select(PaymentTransaction).where(PaymentTransaction.tran_id == a.tran_id)
    ).scalar_one()
    return a, a_row


# Convention "V0" and "at V0": the utcnow patch returns V0 for the step, NOW again after
V0 = datetime(2026, 9, 27, 11, 0, 0)


@contextmanager
def at(when):
    with patch("app.managers.payment_transaction_manager.utcnow", return_value=when):
        yield


# Convention "GHOST": built in memory, never added to the session
def ghost():
    return Profile(id=MISSING, name="Ghost", email="ghost@example.com")


# Convention "commit point"
def commit_point(db, gw):
    db.commit()
    gw.reset_mock()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def reread(db, txn_id):
    db.expire_all()
    return db.get(PaymentTransaction, txn_id)


# unchanged(R)
def snap_txn(db, txn_id):
    row = reread(db, txn_id)
    return {
        a.key: getattr(row, a.key) for a in inspect(PaymentTransaction).column_attrs
    }


# nothing written
def counts(db):
    n_txn = db.execute(
        select(func.count()).select_from(PaymentTransaction)
    ).scalar_one()
    n_ev = db.execute(
        select(func.count()).select_from(PaymentTransactionEvent)
    ).scalar_one()
    return n_txn, n_ev


# x_gone
def x_count(db):
    return db.execute(
        select(func.count())
        .select_from(PaymentTransaction)
        .where(PaymentTransaction.tran_id == E26)
    ).scalar_one()


def rows_in(db, ws_id):
    db.expire_all()
    return list(
        db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.workspace_id == ws_id)
            .order_by(PaymentTransaction.id)
        ).scalars()
    )


def row_by_tran(db, tran_id):
    db.expire_all()
    return db.execute(
        select(PaymentTransaction).where(PaymentTransaction.tran_id == tran_id)
    ).scalar_one()


def count_where(db, *conds):
    return db.execute(
        select(func.count()).select_from(PaymentTransaction).where(*conds)
    ).scalar_one()


def event_rows(db, txn_id):
    db.expire_all()
    return list(
        db.execute(
            select(PaymentTransactionEvent)
            .where(PaymentTransactionEvent.payment_transaction_id == txn_id)
            .order_by(PaymentTransactionEvent.id)
        ).scalars()
    )


# events(R)
def events(db, txn_id):
    return [e.event_type for e in event_rows(db, txn_id)]


def ws_events(db, ws_id):
    return db.execute(
        select(func.count())
        .select_from(PaymentTransactionEvent)
        .where(PaymentTransactionEvent.workspace_id == ws_id)
    ).scalar_one()


def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


def clean(db):
    return not db.new and not db.dirty and not db.deleted


# spies
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# failing commit (the test wraps it in `pytest.raises(RuntimeError)`)
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# failing refresh (the test wraps it in `pytest.raises(RuntimeError)`)
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Statement recorder (listener on the session's connection, During the When only)
@contextmanager
def recorder(db):
    stmts = []
    conn = db.get_bind()

    def _rec(conn_, cursor, statement, parameters, context, executemany):
        stmts.append(statement)

    event.listen(conn, "before_cursor_execute", _rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", _rec)


def selects_pt(s):
    return s.lstrip().upper().startswith("SELECT") and "FROM payment_transactions" in s


def selects_events(s):
    return (
        s.lstrip().upper().startswith("SELECT")
        and "FROM payment_transaction_events" in s
    )


def lock_stmts(stmts):
    return [s for s in stmts if selects_pt(s) and "FOR UPDATE" in s]


def where_part(s):
    return s.split("WHERE", 1)[1] if "WHERE" in s else ""


# "selects from payment_transactions and contains idempotency_key": the key in the WHERE clause
# (every SELECT of the mapped model lists the column; cases rev 2a)
def key_lookups(stmts):
    return [s for s in stmts if selects_pt(s) and "idempotency_key" in where_part(s)]


def order_by_part(s):
    return s.split("ORDER BY", 1)[1] if "ORDER BY" in s else ""


# Race simulation (IK-28, IK-29): first lookup misses, the re-read is the real method
def race_side_effect():
    real = PaymentTransactionDAO.get_by_workspace_and_idempotency_key
    answers = iter([lambda *a, **k: None, real])

    def _se(*a, **k):
        return next(answers)(*a, **k)

    return _se


# xfail markers (Expect column)
def xbug(reason, strict=True):
    return pytest.mark.xfail(strict=strict, reason=reason)


BUG_019 = "BUG-019: Refused checkout start leaves no record and returns 502"
BUG_023 = "BUG-023: Unknown or foreign val_id permanently fails the transaction"
BUG_026 = "BUG-026: Unverified redirect outcome blocks later verified result"
BUG_028 = "BUG-028: Event type names differ from the documented list"
BUG_029 = "BUG-029: Risk-hold resolution does not lock the row"
BUG_1190 = (
    "BUG-1190: Payment timeline steps with one timestamp come back in no fixed order"
)
BUG_1191 = "BUG-1191: Payment event read has no workspace filter"
BUG_2402 = "BUG-2402: Payments of one creation time come back in no fixed order in the ledger list"
BUG_3022 = "BUG-3022: Payment ledger does not show why a start was refused or whether an outcome was gateway-verified"
BUG_3023 = (
    "BUG-3023: Starting the same checkout twice opens two payable gateway sessions"
)
BUG_022 = "BUG-022: Currency code not validated or normalised"


# =========================================================================== #
# _to_response
# =========================================================================== #


# [claude] PTS-TR-01
def test_pts_tr_01__every_stored_field_copied(db, mk_t, w1, u1, u2):
    """PTS-TR-01 — every stored field is copied, with the given name.
    Rules: _to_response R1."""
    t = mk_t(
        status="VALIDATED_SUCCESS",
        val_id="VAL-1",
        risk_level=0,
        risk_title="Safe",
        bank_tran_id="BANK-1",
        card_type="VISA-Brac bank",
        verify_sign="SIG-1",
        value_a="va",
        value_b="vb",
        value_c="vc",
        value_d="vd",
        validated_at=NOW,
        risk_resolved_by=u2.id,
        risk_resolved_at=NOW,
        risk_resolution_note=NOTE,
        last_ipn_payload={"k": "v"},
    )
    result = _to_response(t, initiated_by_name="Karim")
    # Then 1
    assert isinstance(result, PaymentTransactionResponse)
    # Then 2
    assert result.id == t.id
    assert result.workspace_id == w1.id
    assert result.tran_id == A26
    assert result.status == "VALIDATED_SUCCESS"
    # Then 3
    assert result.amount == Decimal("500.00")
    assert result.currency == "BDT"
    assert result.cus_name == "Karim"
    assert result.cus_email == "karim@example.com"
    assert result.cus_phone == "01711000000"
    # Then 4
    assert result.value_a == "va"
    assert result.value_b == "vb"
    assert result.value_c == "vc"
    assert result.value_d == "vd"
    # Then 5
    assert result.session_key == "SESS-0"
    assert result.gateway_page_url == "https://sandbox.example/pay/SESS-0"
    assert result.val_id == "VAL-1"
    assert result.risk_level == 0
    assert result.risk_title == "Safe"
    assert result.bank_tran_id == "BANK-1"
    assert result.card_type == "VISA-Brac bank"
    # Then 6
    assert result.risk_resolved_by == u2.id
    assert result.risk_resolved_at == NOW
    assert result.risk_resolution_note == NOTE
    assert result.validated_at == NOW
    # Then 7
    assert result.initiated_by == u1.id
    assert result.initiated_at == t.initiated_at
    assert result.created_at == t.created_at
    assert result.updated_at == t.updated_at
    # Then 8
    assert result.initiated_by_name == "Karim"
    # Then 9
    assert "verify_sign" not in result.model_dump()
    # Then 10
    assert "last_ipn_payload" not in result.model_dump()


# [claude] PTS-TR-02
def test_pts_tr_02__name_defaults_to_none(db, mk_t):
    """PTS-TR-02 — the name defaults to None.
    Rules: _to_response R1."""
    t = mk_t()
    result = _to_response(t)
    # Then 1
    assert isinstance(result, PaymentTransactionResponse)
    # Then 2
    assert result.tran_id == A26
    # Then 3
    assert result.initiated_by_name is None


# [claude] PTS-TR-03
def test_pts_tr_03__row_not_changed(db, gw, mk_t):
    """PTS-TR-03 — the row is not changed.
    Rules: _to_response R2."""
    t = mk_t()
    commit_point(db, gw)
    before = snap_txn(db, t.id)
    result = _to_response(t, initiated_by_name="Karim")
    # Then 1
    assert result.id == t.id
    # Then 2
    assert clean(db)
    # Then 3
    assert snap_txn(db, t.id) == before


# [claude] PTS-TR-04
@xbug(BUG_3022)
def test_pts_tr_04__failed_reason_and_outcome_verified_in_response(db, mk_t):
    """PTS-TR-04 — BUG-3022: failed_reason and outcome_verified are in the response.
    Rules: _to_response R1a [BUG-3022]."""
    t = mk_t(status="INIT_FAILED", session_key=None, gateway_page_url=None)
    t.failed_reason = "Store is de-active"
    t.outcome_verified = False
    result = _to_response(t)
    # Then 1
    assert result.status == "INIT_FAILED"
    # Then 2
    assert result.failed_reason == "Store is de-active"
    # Then 3
    assert result.outcome_verified is False


# =========================================================================== #
# initiate_payment
# =========================================================================== #


# [claude] PTS-I-01
def test_pts_i_01__accepted_start_committed(db, gw, w1, u1):
    """PTS-I-01 — an accepted start is committed and answered from the saved row.
    Rules: initiate_payment R1, R2, R6; TC1, TC2."""
    with spies(db) as (cm, _rb):
        result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert isinstance(result, InitiatePaymentResponse)
    # Then 2
    assert re.fullmatch(HEX26, result.tran_id)
    # Then 3
    assert result.status == "INITIATED"
    assert result.gateway_page_url == URL1
    # Then 4
    assert result.failed_reason is None
    # Then 5
    assert gw.init_session.call_count == 1
    # Then 6
    assert gw.init_session.call_args.args[0].tran_id == result.tran_id
    # Then 7
    assert gw.validate.call_count == 0
    # Then 8
    assert cm.call_count == 1
    db.rollback()
    # Then 9
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.tran_id == result.tran_id
    assert row.status == "INITIATED"
    assert row.amount == Decimal("500.00")
    assert row.currency == "BDT"
    assert row.cus_name == "Karim"
    assert row.initiated_by == u1.id
    assert row.session_key == "SESS-1"
    assert row.gateway_page_url == URL1
    # Then 10
    assert events(db, row.id) == ["initiated"]
    # Then 11
    e = event_rows(db, row.id)[0]
    assert e.description == "Checkout session created for 500 BDT"
    assert e.performed_by == u1.id
    assert e.metadata_json == {"session_key": "SESS-1"}


# [claude] PTS-I-02
def test_pts_i_02__stored_url_none(db, gw, w1, u1):
    """PTS-I-02 — the answer reads the stored gateway URL, also when the gateway gives none.
    Rules: initiate_payment R2; TC2."""
    gw.init_session.return_value = InitSessionResult(
        status="SUCCESS", session_key=None, gateway_page_url=None
    )
    result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.gateway_page_url is None
    # Then 3
    assert result.failed_reason is None
    db.rollback()
    # Then 4
    row = row_by_tran(db, result.tran_id)
    assert row.status == "INITIATED"
    assert row.gateway_page_url is None


# [claude] PTS-I-03
@xbug(BUG_019)
def test_pts_i_03__refused_start_committed_as_init_failed(db, gw, w1, u1):
    """PTS-I-03 — BUG-019: a refused start is committed and answered as INIT_FAILED.
    Rules: initiate_payment R3, R3a [BUG-019]; Errors row 1."""
    gw.init_session.return_value = REFUSED
    result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert result.status == "INIT_FAILED"
    # Then 2
    assert result.failed_reason == "Store is de-active"
    # Then 3
    assert result.gateway_page_url is None
    # Then 4
    assert re.fullmatch(HEX26, result.tran_id)
    # Then 5
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 6
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == result.tran_id
    assert rows[0].status == "INIT_FAILED"
    assert rows[0].failed_reason == "Store is de-active"
    # Then 7
    assert events(db, rows[0].id) == ["initiation_failed"]


# [claude] PTS-I-04
@xbug(BUG_019)
def test_pts_i_04__refusal_without_reason_unknown_error(db, gw, w1, u1):
    """PTS-I-04 — BUG-019: a refusal without a reason answers "unknown error".
    Rules: initiate_payment R3a [BUG-019]."""
    gw.init_session.return_value = InitSessionResult(
        status="FAILED", failed_reason=None
    )
    result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert result.status == "INIT_FAILED"
    # Then 2
    assert result.failed_reason == "unknown error"
    db.rollback()
    # Then 3
    assert row_by_tran(db, result.tran_id).failed_reason == "unknown error"


# [claude] PTS-I-05
@xbug(BUG_019)
def test_pts_i_05__failing_commit_of_refused_start(db, gw, w1, u1):
    """PTS-I-05 — BUG-019: a failing commit of a refused start saves nothing.
    Rules: initiate_payment R3 [BUG-019]; TC4."""
    gw.init_session.return_value = REFUSED
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(rows_in(db, w1.id)) == 0


# [claude] PTS-I-06
def test_pts_i_06__raising_gateway_passes_same_object(db, gw, w1, u1, mk_x):
    """PTS-I-06 — a raising gateway call passes as the same object and nothing is saved.
    Rules: initiate_payment R4; Errors row 2; TC3."""
    e = TimeoutError("gateway timeout")
    gw.init_session.side_effect = e
    commit_point(db, gw)
    before = counts(db)
    mk_x()
    # Then 1
    with pytest.raises(TimeoutError) as exc:
        svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 2
    assert exc.value is e
    # Then 3
    assert gw.init_session.call_count == 1
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert usable(db)


# [claude] PTS-I-07
def test_pts_i_07__no_free_tran_id_500(db, gw, w1, u1, mk_t, mk_x):
    """PTS-I-07 — no free tran_id: the 500 passes unchanged, no gateway call.
    Rules: initiate_payment R4; Errors row 3; TC3."""
    for d in "12345":
        mk_t(tran_id=d * 26)
    commit_point(db, gw)
    before = counts(db)
    mk_x()
    with patch(
        "app.managers.payment_transaction_manager.secrets.token_hex",
        side_effect=["1" * 26, "2" * 26, "3" * 26, "4" * 26, "5" * 26, "6" * 26],
    ):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 2
    assert exc.value.status_code == 500
    # Then 3
    assert exc.value.detail == "Could not generate a unique transaction ID"
    # Then 4
    assert gw.init_session.call_count == 0
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert count_where(db, PaymentTransaction.tran_id == "6" * 26) == 0
    # Then 7
    assert counts(db) == before


# [claude] PTS-I-08
def test_pts_i_08__invalid_amount_refused_by_schema(db, gw, w1):
    """PTS-I-08 — an invalid amount is refused by the schema before the service.
    Rules: initiate_payment R4 (schema ValidationError)."""
    # Then 1
    with pytest.raises(pydantic.ValidationError):
        InitiatePaymentRequest(
            amount=Decimal(0), currency="BDT", cus_phone="01711000000"
        )
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert len(rows_in(db, w1.id)) == 0


# [claude] PTS-I-09
def test_pts_i_09__failure_after_session_opened(db, gw, u1, mk_x):
    """PTS-I-09 — a failure after the session was opened saves nothing and returns no URL.
    Rules: initiate_payment R5, R6; TC3."""
    commit_point(db, gw)
    before = counts(db)
    mk_x()
    # Then 1
    with pytest.raises(IntegrityError):
        svc.initiate_payment(db, workspace_id=MISSING, user=u1, request=req())
    # Then 2
    assert gw.init_session.call_count == 1
    # Then 3
    assert count_where(db, PaymentTransaction.workspace_id == MISSING) == 0
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert usable(db)


# [claude] PTS-I-10
def test_pts_i_10__failing_commit_rolled_back(db, gw, w1, u1):
    """PTS-I-10 — a failing commit is rolled back, the gateway was called once and not again.
    Rules: initiate_payment R5, R6; Errors row 5; TC4."""
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert gw.init_session.call_count == 1
    # Then 4
    assert len(rows_in(db, w1.id)) == 0
    # Then 5
    assert ws_events(db, w1.id) == 0


# [claude] PTS-I-11
def test_pts_i_11__failing_refresh_leaves_attempt_saved(db, w1, u1):
    """PTS-I-11 — a failing re-read leaves the attempt saved.
    Rules: initiate_payment R8; TC5."""
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].status == "INITIATED"
    assert rows[0].session_key == "SESS-1"
    # Then 3
    assert events(db, rows[0].id) == ["initiated"]


# [claude] PTS-I-12
def test_pts_i_12__two_calls_without_key_two_attempts(db, gw, w1, u1):
    """PTS-I-12 — two calls without a key make two attempts.
    Rules: initiate_payment R7."""
    a = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    commit_point(db, gw)
    result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.tran_id != a.tran_id
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    rows = rows_in(db, w1.id)
    assert len(rows) == 2
    # Then 5
    assert {r.tran_id for r in rows} == {a.tran_id, result.tran_id}


# [claude] PTS-I-13
def test_pts_i_13__start_in_w2_stored_in_w2_only(db, w0, w1, w2, u3):
    """PTS-I-13 — an accepted start in W2 is stored in W2 only.
    Rules: initiate_payment R1."""
    result = svc.initiate_payment(db, workspace_id=w2.id, user=u3, request=req())
    # Then 1
    assert result.status == "INITIATED"
    db.rollback()
    # Then 2
    rows = rows_in(db, w2.id)
    assert len(rows) == 1
    assert rows[0].tran_id == result.tran_id
    assert rows[0].initiated_by == u3.id
    # Then 3
    assert len(rows_in(db, w1.id)) == 0
    # Then 4
    assert len(rows_in(db, w0.id)) == 0


# =========================================================================== #
# initiate_payment — idempotency (BUG-3023)
# =========================================================================== #


# [claude] PTS-IK-01
@xbug(BUG_3023)
def test_pts_ik_01__new_key_stores_key_and_fingerprint(db, gw, w1, u1):
    """PTS-IK-01 — a new key starts an attempt; the key and its fingerprint are stored.
    Rules: initiate_payment R7a, R7a1, R7c1 [BUG-3023]."""
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.status == "INITIATED"
    assert result.gateway_page_url == URL1
    # Then 2
    assert result.failed_reason is None
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == result.tran_id
    assert rows[0].idempotency_key == "K-1"
    # Then 5
    assert rows[0].idempotency_fingerprint == fpx(u1)
    # Then 6
    assert events(db, rows[0].id) == ["initiated"]


# [claude] PTS-IK-02
@xbug(BUG_3023 + "; " + BUG_019)
def test_pts_ik_02__refused_start_stores_key_and_fingerprint(db, gw, w1, u1):
    """PTS-IK-02 — a refused start stores the key and the fingerprint too.
    Rules: initiate_payment R7a, R7a1 [BUG-3023] (needs BUG-019)."""
    gw.init_session.return_value = REFUSED
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.status == "INIT_FAILED"
    # Then 2
    assert result.failed_reason == "Store is de-active"
    db.rollback()
    # Then 3
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].status == "INIT_FAILED"
    assert rows[0].idempotency_key == "K-1"
    # Then 4
    assert rows[0].idempotency_fingerprint == fpx(u1)


# [claude] PTS-IK-03
@xbug(BUG_3023)
def test_pts_ik_03__same_key_same_body_replays(db, gw, w1, u1, mk_x):
    """PTS-IK-03 — same key, same body: the stored attempt is returned, no gateway call, nothing written.
    Rules: initiate_payment R7b, R7b1 [BUG-3023]."""
    a, a_row = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    before = counts(db)
    before_a = snap_txn(db, a_row.id)
    mk_x()
    with spies(db) as (cm, rb):
        result = svc.initiate_payment(
            db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
        )
    # Then 1
    assert isinstance(result, InitiatePaymentResponse)
    # Then 2
    assert result.tran_id == a.tran_id
    # Then 3
    assert result.status == "INITIATED"
    assert result.gateway_page_url == URL1
    # Then 4
    assert result.failed_reason is None
    # Then 5
    assert gw.init_session.call_count == 0
    # Then 6
    assert cm.call_count == 0
    # Then 7
    assert rb.call_count == 1
    # Then 8
    assert clean(db)
    # Then 9
    assert x_count(db) == 0
    # Then 10
    assert counts(db) == before
    # Then 11
    assert events(db, a_row.id) == ["initiated"]
    # Then 12
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-04
@xbug(BUG_3023 + "; " + BUG_019)
def test_pts_ik_04__same_key_on_refused_replays_init_failed(db, gw, w1, u1):
    """PTS-IK-04 — same key on a refused attempt replays INIT_FAILED with its reason.
    Rules: initiate_payment R7b [BUG-3023] (needs BUG-019)."""
    gw.init_session.return_value = REFUSED
    a, _a_row = first(db, w1.id, u1, req(), K)
    gw.init_session.return_value = OKS
    commit_point(db, gw)
    before = counts(db)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert result.status == "INIT_FAILED"
    # Then 3
    assert result.failed_reason == "Store is de-active"
    # Then 4
    assert result.gateway_page_url is None
    # Then 5
    assert gw.init_session.call_count == 0
    # Then 6
    assert counts(db) == before


# [claude] PTS-IK-05
@xbug(BUG_3023)
def test_pts_ik_05__same_key_after_paid_shows_current_status(db, gw, w1, u1):
    """PTS-IK-05 — same key after the attempt was paid shows the current status.
    Rules: initiate_payment R7b [BUG-3023]."""
    a, a_row = first(db, w1.id, u1, req(), K)
    paid(db, gw, a_row)
    commit_point(db, gw)
    before = counts(db)
    before_a = snap_txn(db, a_row.id)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert result.status == "VALIDATED_SUCCESS"
    # Then 3
    assert result.gateway_page_url == URL1
    # Then 4
    assert gw.init_session.call_count == 0
    # Then 5
    assert gw.validate.call_count == 0
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-06
@xbug(BUG_3023)
def test_pts_ik_06__same_key_different_amount_409(db, gw, w1, u1, mk_x):
    """PTS-IK-06 — same key, different amount: 409, nothing written, no gateway call.
    Rules: initiate_payment R7c [BUG-3023]; Errors row 4; TC3."""
    _a, a_row = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    before = counts(db)
    before_a = snap_txn(db, a_row.id)
    mk_x()
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.initiate_payment(
                db,
                workspace_id=w1.id,
                user=u1,
                request=req(amount=Decimal(600)),
                idempotency_key=K,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == IDEM409
    # Then 4
    assert gw.init_session.call_count == 0
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert rb.call_count == 1
    # Then 7
    assert x_count(db) == 0
    # Then 8
    assert counts(db) == before
    # Then 9
    assert snap_txn(db, a_row.id) == before_a
    # Then 10
    assert usable(db)


def _ik_409_one_field(db, gw, w1, u1, changed):
    first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.initiate_payment(
            db, workspace_id=w1.id, user=u1, request=req(**changed), idempotency_key=K
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == IDEM409
    # Then 3
    assert gw.init_session.call_count == 0
    # Then 4
    assert counts(db) == before


# [claude] PTS-IK-07 … PTS-IK-14 (identical setup and checks, one changed field each)
@xbug(BUG_3023)
@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"currency": "USD"}, id="PTS-IK-07"),
        pytest.param({"cus_name": "Other Name"}, id="PTS-IK-08"),
        pytest.param({"cus_email": "other@example.com"}, id="PTS-IK-09"),
        pytest.param({"cus_phone": "01811000000"}, id="PTS-IK-10"),
        pytest.param({"value_a": "plan:pro"}, id="PTS-IK-11"),
        pytest.param({"value_b": "b-val"}, id="PTS-IK-12"),
        pytest.param({"value_c": "c-val"}, id="PTS-IK-13"),
        pytest.param({"value_d": "d-val"}, id="PTS-IK-14"),
    ],
)
def test_pts_ik_07_14__same_key_one_field_changed_409(db, gw, w1, u1, changed):
    """PTS-IK-07 … PTS-IK-14 — same key, one request field changed (currency, cus_name, cus_email,
    cus_phone, value_a … value_d): 409, no gateway call, nothing written.
    Rules: initiate_payment R7c [BUG-3023]."""
    _ik_409_one_field(db, gw, w1, u1, changed)


# [claude] PTS-IK-15
@xbug(BUG_3023)
def test_pts_ik_15__another_member_same_body_409(db, gw, w1, u1, u2, mk_x):
    """PTS-IK-15 — same key, same body, another member of the workspace: 409.
    Rules: initiate_payment R7c, R7c1 [BUG-3023]."""
    _a, a_row = first(
        db, w1.id, u1, req(cus_name="Karim", cus_email="karim@example.com"), K
    )
    commit_point(db, gw)
    before = counts(db)
    before_a = snap_txn(db, a_row.id)
    mk_x()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.initiate_payment(
            db,
            workspace_id=w1.id,
            user=u2,
            request=req(cus_name="Karim", cus_email="karim@example.com"),
            idempotency_key=K,
        )
    assert exc.value.status_code == 409
    # Then 2
    assert (
        exc.value.detail
        == "This idempotency key was already used for a different payment"
    )
    # Then 3
    assert gw.init_session.call_count == 0
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-16
@xbug(BUG_3023)
def test_pts_ik_16__key_in_w0_does_not_touch_w1(db, gw, w0, w1, u1, u3):
    """PTS-IK-16 — the key used only in W0 does not touch a call in W1.
    Rules: initiate_payment R7d [BUG-3023]; HR-16."""
    a, a_row = first(db, w0.id, u3, req(), K)
    commit_point(db, gw)
    before_a = snap_txn(db, a_row.id)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.tran_id != a.tran_id
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == result.tran_id
    assert rows[0].idempotency_key == "K-1"
    assert rows[0].initiated_by == u1.id
    # Then 5
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-17
@xbug(BUG_3023)
def test_pts_ik_17__key_in_w2_does_not_touch_w1(db, gw, w1, w2, u1, u3):
    """PTS-IK-17 — the key used only in W2 does not touch a call in W1.
    Rules: initiate_payment R7d [BUG-3023]; HR-16."""
    a, a_row = first(db, w2.id, u3, req(), K)
    commit_point(db, gw)
    before_a = snap_txn(db, a_row.id)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.tran_id != a.tran_id
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == result.tran_id
    assert rows[0].idempotency_key == "K-1"
    # Then 5
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-18
@xbug(BUG_3023)
def test_pts_ik_18__key_in_w1_other_body_no_409_in_w2(db, gw, w1, w2, u1, u3):
    """PTS-IK-18 — the key used in W1 with another body does not give 409 in W2.
    Rules: initiate_payment R7d [BUG-3023]; HR-16."""
    a, a_row = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    before_a = snap_txn(db, a_row.id)
    result = svc.initiate_payment(
        db,
        workspace_id=w2.id,
        user=u3,
        request=req(amount=Decimal(700)),
        idempotency_key=K,
    )
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.tran_id != a.tran_id
    # Then 3
    assert result.gateway_page_url == URL1
    # Then 4
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 5
    rows = rows_in(db, w2.id)
    assert len(rows) == 1
    assert rows[0].amount == Decimal("700.00")
    assert rows[0].idempotency_key == "K-1"
    # Then 6
    assert snap_txn(db, a_row.id) == before_a


# [claude] PTS-IK-19
@xbug(BUG_3023)
def test_pts_ik_19__key_in_w1_and_w2_new_attempt_in_w0(db, gw, w0, w1, w2, u1, u3):
    """PTS-IK-19 — the key used in W1 and W2, a call in W0 is a new attempt.
    Rules: initiate_payment R7d [BUG-3023]; HR-16."""
    a1, _ = first(db, w1.id, u1, req(), K)
    a2, _ = first(db, w2.id, u3, req(), K)
    commit_point(db, gw)
    result = svc.initiate_payment(
        db, workspace_id=w0.id, user=u3, request=req(), idempotency_key=K
    )
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    assert result.tran_id not in {a1.tran_id, a2.tran_id}
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    rows = rows_in(db, w0.id)
    assert len(rows) == 1
    assert rows[0].idempotency_key == "K-1"
    # Then 5
    assert len(rows_in(db, w1.id)) == 1
    assert len(rows_in(db, w2.id)) == 1


# [claude] PTS-IK-20
@xbug(BUG_3023)
def test_pts_ik_20__no_key_next_to_stored_key_new_attempt(db, gw, w1, u1):
    """PTS-IK-20 — a call without a key next to a stored key is a new attempt.
    Rules: initiate_payment R7, R7a1, R7b [BUG-3023]."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    result = svc.initiate_payment(db, workspace_id=w1.id, user=u1, request=req())
    # Then 1
    assert result.tran_id != a.tran_id
    # Then 2
    assert result.status == "INITIATED"
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    assert len(rows_in(db, w1.id)) == 2
    # Then 5
    row = row_by_tran(db, result.tran_id)
    assert row.idempotency_key is None
    # Then 6
    assert row.idempotency_fingerprint is None


def _ik_other_key(db, gw, w1, u1, stored_key, sent_key):
    a, _ = first(db, w1.id, u1, req(), stored_key)
    commit_point(db, gw)
    result = svc.initiate_payment(
        db,
        workspace_id=w1.id,
        user=u1,
        request=req(amount=Decimal(600)),
        idempotency_key=sent_key,
    )
    return a, result


# [claude] PTS-IK-21
@xbug(BUG_3023)
def test_pts_ik_21__key_in_other_capitals_is_another_key(db, gw, w1, u1):
    """PTS-IK-21 — a key in other capitals is another key.
    Rules: initiate_payment Inputs (key compared exactly), R7a [BUG-3023]."""
    a, result = _ik_other_key(db, gw, w1, u1, K, "k-1")
    # Then 1
    assert result.tran_id != a.tran_id
    # Then 2
    assert result.status == "INITIATED"
    # Then 3
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 4
    assert row_by_tran(db, result.tran_id).idempotency_key == "k-1"


# [claude] PTS-IK-22
@xbug(BUG_3023)
def test_pts_ik_22__key_with_leading_space_is_another_key(db, gw, w1, u1):
    """PTS-IK-22 — a key with a leading space is another key.
    Rules: initiate_payment Inputs (key compared exactly), R7a [BUG-3023]."""
    a, result = _ik_other_key(db, gw, w1, u1, K, " K-1")
    # Then 1
    assert result.tran_id != a.tran_id
    # Then 2
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 3
    assert row_by_tran(db, result.tran_id).idempotency_key == " K-1"


# [claude] PTS-IK-23
@xbug(BUG_3023)
def test_pts_ik_23__part_of_stored_key_is_another_key(db, gw, w1, u1):
    """PTS-IK-23 — a part of a stored key is another key.
    Rules: initiate_payment Inputs (key compared exactly), R7a [BUG-3023]."""
    a, result = _ik_other_key(db, gw, w1, u1, "XK-1Y", K)
    # Then 1
    assert result.tran_id != a.tran_id
    # Then 2
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 3
    assert row_by_tran(db, result.tran_id).idempotency_key == "K-1"


# [claude] PTS-IK-24
@xbug(BUG_3023)
def test_pts_ik_24__underscore_in_key_is_literal(db, gw, w1, u1):
    """PTS-IK-24 — `_` in a key is literal.
    Rules: initiate_payment Inputs (key compared exactly), R7a [BUG-3023]."""
    a, result = _ik_other_key(db, gw, w1, u1, K, "K_1")
    # Then 1
    assert result.tran_id != a.tran_id
    # Then 2
    assert gw.init_session.call_count == 1
    db.rollback()
    # Then 3
    assert row_by_tran(db, result.tran_id).idempotency_key == "K_1"


# [claude] PTS-IK-25
@xbug(BUG_3023)
def test_pts_ik_25__unique_index_exists_as_specified(db):
    """PTS-IK-25 — the unique index ix_payment_transactions_workspace_idempotency_key exists as specified.
    Rules: initiate_payment R7a1, R7e [BUG-3023]."""
    rows = (
        db.execute(
            text(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_payment_transactions_workspace_idempotency_key'"
            )
        )
        .scalars()
        .all()
    )
    # Then 1
    assert len(rows) == 1
    # Then 2
    assert rows[0] == (
        "CREATE UNIQUE INDEX ix_payment_transactions_workspace_idempotency_key ON public.payment_transactions "
        "USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)"
    )


# [claude] PTS-IK-26
@xbug(BUG_3023)
def test_pts_ik_26__two_rows_one_key_one_workspace_refused(db, gw, w1, u1, mk_t):
    """PTS-IK-26 — two rows with one key in one workspace are refused by the database.
    Rules: initiate_payment R7a1, R7e [BUG-3023]."""
    mk_t(idempotency_key="K-1", idempotency_fingerprint="0" * 64)
    commit_point(db, gw)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(
                PaymentTransaction(
                    **t_fields(
                        w1,
                        u1,
                        tran_id=B26,
                        idempotency_key="K-1",
                        idempotency_fingerprint="1" * 64,
                    )
                )
            )
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "ix_payment_transactions_workspace_idempotency_key" in str(exc.value.orig)
    # Then 4
    assert count_where(db, PaymentTransaction.idempotency_key == "K-1") == 1


# [claude] PTS-IK-27
@xbug(BUG_3023)
def test_pts_ik_27__one_key_per_workspace_many_without_key(db, w0, w1, w2, mk_t):
    """PTS-IK-27 — the index allows one key per workspace and many rows without a key.
    Rules: initiate_payment R7, R7a1, R7d [BUG-3023]."""
    mk_t(workspace_id=w0.id, idempotency_key="K-1", idempotency_fingerprint="0" * 64)
    mk_t(tran_id=B26, idempotency_key="K-1", idempotency_fingerprint="0" * 64)
    mk_t(
        workspace_id=w2.id,
        tran_id=C26,
        idempotency_key="K-1",
        idempotency_fingerprint="0" * 64,
    )
    mk_t(tran_id="1" * 26, idempotency_key=None, idempotency_fingerprint=None)
    mk_t(tran_id="2" * 26, idempotency_key=None, idempotency_fingerprint=None)
    # Then 1
    assert count_where(db, PaymentTransaction.idempotency_key == "K-1") == 3
    # Then 2
    assert (
        count_where(
            db,
            PaymentTransaction.workspace_id == w1.id,
            PaymentTransaction.idempotency_key.is_(None),
        )
        == 2
    )


# [claude] PTS-IK-28
@xbug(BUG_3023)
def test_pts_ik_28__race_loser_same_body_replays(db, gw, w1, u1):
    """PTS-IK-28 — the race loser with the same body answers with the winner's attempt, never 500.
    Rules: initiate_payment R7e, R7e2, R7b [BUG-3023]; Errors row "lost the race"."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    gw.init_session.return_value = SESS2
    with patch.object(
        PaymentTransactionDAO,
        "get_by_workspace_and_idempotency_key",
        autospec=True,
        side_effect=race_side_effect(),
    ):
        with spies(db) as (cm, rb):
            result = svc.initiate_payment(
                db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
            )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert result.status == "INITIATED"
    # Then 3
    assert result.gateway_page_url == URL1
    # Then 4
    assert gw.init_session.call_count == 1
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert rb.call_count >= 1
    # Then 7
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == a.tran_id
    # Then 8
    assert count_where(db, PaymentTransaction.session_key == "SESS-2") == 0
    # Then 9
    assert usable(db)


# [claude] PTS-IK-29
@xbug(BUG_3023)
def test_pts_ik_29__race_loser_different_body_409(db, gw, w1, u1):
    """PTS-IK-29 — the race loser with a different body answers 409, never 500.
    Rules: initiate_payment R7e, R7e2, R7c [BUG-3023]."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    gw.init_session.return_value = SESS2
    with patch.object(
        PaymentTransactionDAO,
        "get_by_workspace_and_idempotency_key",
        autospec=True,
        side_effect=race_side_effect(),
    ):
        with spies(db) as (_cm, rb):
            # Then 1
            with pytest.raises(HTTPException) as exc:
                svc.initiate_payment(
                    db,
                    workspace_id=w1.id,
                    user=u1,
                    request=req(amount=Decimal(600)),
                    idempotency_key=K,
                )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert (
        exc.value.detail
        == "This idempotency key was already used for a different payment"
    )
    # Then 4
    assert gw.init_session.call_count == 1
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == a.tran_id
    # Then 7
    assert count_where(db, PaymentTransaction.amount == Decimal("600.00")) == 0
    # Then 8
    assert usable(db)


# [claude] PTS-IK-30
@xbug(BUG_3023)
def test_pts_ik_30__replay_sends_no_write_and_no_tran_id_check(db, gw, w1, u1):
    """PTS-IK-30 — a replay sends no INSERT or UPDATE and never generates a tran_id.
    Rules: initiate_payment R7b, R7b1, R7e1 [BUG-3023]."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    with recorder(db) as stmts:
        result = svc.initiate_payment(
            db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
        )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert not [s for s in stmts if s.lstrip().upper().startswith(("INSERT", "UPDATE"))]
    # Then 4
    pt_selects = [s for s in stmts if selects_pt(s)]
    assert pt_selects == key_lookups(stmts)


# [claude] PTS-IK-31
@xbug(BUG_3023)
def test_pts_ik_31__lookup_single_table_no_lock_first(db, w1, u1):
    """PTS-IK-31 — the key lookup is a single-table read with no lock, sent first.
    Rules: initiate_payment R7e1 [BUG-3023]."""
    with recorder(db) as stmts:
        result = svc.initiate_payment(
            db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
        )
    # Then 1
    assert result.status == "INITIATED"
    # Then 2
    lookups = key_lookups(stmts)
    assert len(lookups) == 1
    lookup = lookups[0]
    # Then 3
    assert "FOR UPDATE" not in lookup
    # Then 4
    assert "JOIN" not in lookup.upper()
    # Then 5
    i_lookup = stmts.index(lookup)
    assert all(
        i_lookup < i
        for i, s in enumerate(stmts)
        if "payment_transactions" in s and s is not lookup
    )


def _ik_replay(db, gw, w1, u1, stored_req, sent_req):
    a, _ = first(db, w1.id, u1, stored_req, K)
    commit_point(db, gw)
    before = counts(db)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=sent_req, idempotency_key=K
    )
    return a, result, before


# [claude] PTS-IK-32
@xbug(BUG_3023)
def test_pts_ik_32__amount_500_00_after_500_replays(db, gw, w1, u1):
    """PTS-IK-32 — amount 500.00 after 500 is the same body: replay.
    Rules: initiate_payment R7c1 (amount by value), R7b [BUG-3023]."""
    a, result, before = _ik_replay(db, gw, w1, u1, req(), req(amount=Decimal("500.00")))
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-33
@xbug(BUG_3023)
def test_pts_ik_33__empty_name_after_omitted_replays(db, gw, w1, u1):
    """PTS-IK-33 — cus_name "" after an omitted name is the same body: replay.
    Rules: initiate_payment R7c1 (blank text = null) [BUG-3023]."""
    a, result, before = _ik_replay(db, gw, w1, u1, req(), req(cus_name=""))
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-34
@xbug(BUG_3023)
def test_pts_ik_34__bdt_after_omitted_currency_replays(db, gw, w1, u1):
    """PTS-IK-34 — currency "BDT" after an omitted currency is the same body: replay.
    Rules: initiate_payment R7c1 (omitted = default) [BUG-3023]."""
    a, result, before = _ik_replay(db, gw, w1, u1, req0(), req())
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-35
@xbug(BUG_3023)
def test_pts_ik_35__name_with_outer_spaces_replays(db, gw, w1, u1):
    """PTS-IK-35 — a name with outer spaces is the same body as the trimmed name: replay.
    Rules: initiate_payment R7c1 (text trimmed) [BUG-3023]."""
    a, result, before = _ik_replay(
        db, gw, w1, u1, req(cus_name="Ali"), req(cus_name=" Ali ")
    )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-36
@xbug(BUG_3023)
def test_pts_ik_36__fingerprint_reproduces_spec_example(db, w1):
    """PTS-IK-36 — the stored fingerprint reproduces the spec's worked example.
    Rules: initiate_payment R7a1, R7c1 (worked example) [BUG-3023]."""
    p7 = make_profile(db, id=7)
    result = svc.initiate_payment(
        db,
        workspace_id=w1.id,
        user=p7,
        request=InitiatePaymentRequest(
            amount=Decimal("500"),  # noqa: FURB157 (as the card writes it)
            currency="BDT",
            cus_phone="01700000000",
        ),
        idempotency_key=K,
    )
    # Then 1
    assert result.status == "INITIATED"
    db.rollback()
    # Then 2
    assert (
        json.dumps(
            {
                "amount": "500",
                "currency": "BDT",
                "cus_email": None,
                "cus_name": None,
                "cus_phone": "01700000000",
                "profile_id": 7,
                "value_a": None,
                "value_b": None,
                "value_c": None,
                "value_d": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        == '{"amount":"500","currency":"BDT","cus_email":null,"cus_name":null,"cus_phone":"01700000000","profile_id":7,"value_a":null,"value_b":null,"value_c":null,"value_d":null}'
    )
    # Then 3
    assert (
        row_by_tran(db, result.tran_id).idempotency_fingerprint
        == "0bbacdbcb2eb158eba9bfab58060dd04bea674cddc22a51a78dd49db87a949bd"
    )


# [claude] PTS-IK-37
@xbug(BUG_3023)
def test_pts_ik_37__name_in_other_case_409(db, gw, w1, u1):
    """PTS-IK-37 — a name in other case is a different body: 409.
    Rules: initiate_payment R7c1 (case kept), R7c [BUG-3023]."""
    first(db, w1.id, u1, req(cus_name="Ali"), K)
    commit_point(db, gw)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.initiate_payment(
            db,
            workspace_id=w1.id,
            user=u1,
            request=req(cus_name="ali"),
            idempotency_key=K,
        )
    assert exc.value.status_code == 409
    # Then 2
    assert (
        exc.value.detail
        == "This idempotency key was already used for a different payment"
    )
    # Then 3
    assert gw.init_session.call_count == 0
    # Then 4
    assert counts(db) == before


# [claude] PTS-IK-38
@xbug(BUG_3023 + "; " + BUG_022)
def test_pts_ik_38__lowercase_bdt_after_bug_022_replays(db, gw, w1, u1):
    """PTS-IK-38 — after BUG-022, currency "bdt" is the same body as "BDT": replay.
    Rules: initiate_payment R7c1 (currency as the schema leaves it) [BUG-3023] (needs BUG-022)."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    before = counts(db)
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(currency="bdt"), idempotency_key=K
    )
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-39
@xbug(BUG_3023)
def test_pts_ik_39__whitespace_value_a_replays(db, gw, w1, u1):
    """PTS-IK-39 — a whitespace-only value_a is the same body as an omitted one: replay.
    Rules: initiate_payment R7c1 (whitespace-only = null) [BUG-3023]."""
    a, result, before = _ik_replay(db, gw, w1, u1, req(), req(value_a="   "))
    # Then 1
    assert result.tran_id == a.tran_id
    # Then 2
    assert gw.init_session.call_count == 0
    # Then 3
    assert counts(db) == before


# [claude] PTS-IK-40
@xbug(BUG_3023)
def test_pts_ik_40__key_of_100_chars_stored_exactly(db, w1, u1):
    """PTS-IK-40 — a key of 100 characters is stored exactly as sent.
    Rules: initiate_payment Inputs (key String(100), never trimmed), R7a1 [BUG-3023]."""
    result = svc.initiate_payment(
        db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=" K" * 50
    )
    # Then 1
    assert result.status == "INITIATED"
    db.rollback()
    # Then 2
    assert row_by_tran(db, result.tran_id).idempotency_key == " K" * 50


# [claude] PTS-IK-41
@xbug(BUG_3023)
def test_pts_ik_41__key_of_101_chars_data_error(db, gw, w1, u1, mk_x):
    """PTS-IK-41 — a key of 101 characters passed directly: DataError, nothing saved.
    Rules: initiate_payment Inputs (length checked only at the endpoint) [BUG-3023]; TC3."""
    commit_point(db, gw)
    before = counts(db)
    mk_x()
    # Then 1
    with pytest.raises(DataError):
        svc.initiate_payment(
            db, workspace_id=w1.id, user=u1, request=req(), idempotency_key="K" * 101
        )
    # Then 2
    assert x_count(db) == 0
    # Then 3
    assert counts(db) == before
    # Then 4
    assert usable(db)


# [claude] PTS-IK-42
@xbug(BUG_3023)
def test_pts_ik_42__other_integrity_error_reraised(db, gw, u1, mk_x):
    """PTS-IK-42 — an IntegrityError on another constraint is re-raised unchanged.
    Rules: initiate_payment R7e2 (other IntegrityError) [BUG-3023]; Errors row "another constraint"."""
    commit_point(db, gw)
    before = counts(db)
    mk_x()
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.initiate_payment(
            db, workspace_id=MISSING, user=u1, request=req(), idempotency_key=K
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert gw.init_session.call_count == 1
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert counts(db) == before


# [claude] PTS-IK-43
@xbug(BUG_3023)
def test_pts_ik_43__key_index_error_reread_miss_reraised(db, gw, w1, u1):
    """PTS-IK-43 — a key-index IntegrityError whose re-read finds no row is re-raised.
    Rules: initiate_payment R7e2 (re-read miss) [BUG-3023]; Errors row "winner's row not found"."""
    a, _ = first(db, w1.id, u1, req(), K)
    commit_point(db, gw)
    with patch.object(
        PaymentTransactionDAO,
        "get_by_workspace_and_idempotency_key",
        autospec=True,
        side_effect=[None, None],
    ):
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            svc.initiate_payment(
                db, workspace_id=w1.id, user=u1, request=req(), idempotency_key=K
            )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    rows = rows_in(db, w1.id)
    assert len(rows) == 1
    assert rows[0].tran_id == a.tran_id
    # Then 4
    assert usable(db)


# Race simulation (IK-46): first lookup misses; the second answer would restore the key,
# commit, then run the real method (never reached when the other IntegrityError is re-raised)
def ik46_side_effect(db, a_row):
    real = PaymentTransactionDAO.get_by_workspace_and_idempotency_key

    def restore_then_real(*a, **k):
        a_row.idempotency_key = K
        db.commit()
        return real(*a, **k)

    answers = iter([lambda *a, **k: None, restore_then_real])

    def _se(*a, **k):
        return next(answers)(*a, **k)

    return _se


# [claude] PTS-IK-46
@xbug(BUG_3023)
def test_pts_ik_46__non_key_integrity_error_reraised_not_replayed(db, gw, w1, u1):
    """PTS-IK-46 — a non-key IntegrityError while a matching keyed winner exists is re-raised, not replayed.
    Rules: initiate_payment R7e2 (an IntegrityError on any other constraint is re-raised) [BUG-3023]; Errors row "another constraint"."""
    _a, a_row = first(db, w1.id, u1, req(), K)
    a_row.idempotency_key = None
    db.flush()
    commit_point(db, gw)
    with patch.object(
        PaymentTransactionDAO,
        "get_by_workspace_and_idempotency_key",
        autospec=True,
        side_effect=ik46_side_effect(db, a_row),
    ) as lk:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            svc.initiate_payment(
                db, workspace_id=w1.id, user=ghost(), request=req(), idempotency_key=K
            )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert lk.call_count == 1
    # Then 4
    assert gw.init_session.call_count == 1
    # Then 5
    assert (
        db.scalar(
            select(func.count())
            .select_from(PaymentTransaction)
            .where(PaymentTransaction.initiated_by == MISSING)
        )
        == 0
    )
    # Then 6
    assert reread(db, a_row.id).idempotency_key is None
    # Then 7
    assert usable(db)


# [claude] PTS-IK-44
@xbug(BUG_3023)
def test_pts_ik_44__status_change_keeps_key_and_fingerprint(db, gw, w1, u1):
    """PTS-IK-44 — a later status change keeps the key and the fingerprint.
    Rules: initiate_payment R7a1 (written only on insert) [BUG-3023]."""
    a, a_row = first(db, w1.id, u1, req(), K)
    gw.validate.return_value = OKV(a.tran_id)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(
        db, tran_id=a.tran_id, val_id="VAL-1", source="ipn"
    )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    db.rollback()
    # Then 2
    row = reread(db, a_row.id)
    assert row.idempotency_key == "K-1"
    # Then 3
    assert row.idempotency_fingerprint == fpx(u1)


# [claude] PTS-IK-45
@xbug(BUG_3023)
def test_pts_ik_45__fingerprint_writes_500_5_and_trimmed_name(db, w1, u1):
    """PTS-IK-45 — the stored fingerprint writes 500.50 as "500.5" and a trimmed name with its case.
    Rules: initiate_payment R7a1, R7c1 (amount, text) [BUG-3023]."""
    result = svc.initiate_payment(
        db,
        workspace_id=w1.id,
        user=u1,
        request=req(amount=Decimal("500.50"), cus_name=" Ali "),
        idempotency_key=K,
    )
    # Then 1
    assert result.status == "INITIATED"
    db.rollback()
    # Then 2
    assert row_by_tran(db, result.tran_id).idempotency_fingerprint == fp(
        {**fpo(u1), "amount": "500.5", "cus_name": "Ali"}
    )


# =========================================================================== #
# handle_gateway_callback
# =========================================================================== #


# [claude] PTS-GC-01
def test_pts_gc_01__verified_ipn_committed(db, gw, mk_t):
    """PTS-GC-01 — a verified IPN is committed and the row is returned re-read.
    Rules: handle_gateway_callback R1, R5; TC1, TC2."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    unloaded = inspect(result).unloaded
    assert "status" not in unloaded
    assert "updated_at" not in unloaded
    assert "validated_at" not in unloaded
    assert "val_id" not in unloaded
    # Then 2
    assert isinstance(result, PaymentTransaction)
    assert result.id == t.id
    # Then 3
    assert result.status == "VALIDATED_SUCCESS"
    # Then 4
    assert gw.validate.call_count == 1
    assert gw.validate.call_args.args == ("VAL-1",)
    db.rollback()
    # Then 5
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.val_id == "VAL-1"
    assert row.bank_tran_id == "BANK-1"
    assert row.validated_at == NOW
    # Then 6
    assert events(db, t.id) == ["ipn_received", "validated_success"]


# [claude] PTS-GC-02
def test_pts_gc_02__risky_ipn_risk_hold(db, gw, mk_t):
    """PTS-GC-02 — a risky IPN is committed as RISK_HOLD.
    Rules: handle_gateway_callback R1."""
    t = mk_t()
    gw.validate.return_value = RISKY(A26)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    assert result.id == t.id
    assert result.status == "RISK_HOLD"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "RISK_HOLD"
    assert row.risk_level == 1
    assert row.risk_title == "Suspicious card"
    # Then 3
    assert events(db, t.id) == ["ipn_received", "risk_hold"]


# [claude] PTS-GC-03
def test_pts_gc_03__same_ipn_again_duplicate_ignored(db, gw, mk_t):
    """PTS-GC-03 — the same IPN again: RISK_HOLD and its stamp stay, one duplicate_ignored is committed.
    Rules: handle_gateway_callback R2, R5."""
    t = mk_t()
    with at(V0):
        held(db, gw, t)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    assert result.id == t.id
    assert result.status == "RISK_HOLD"
    # Then 2
    assert gw.validate.call_count == 0
    db.rollback()
    # Then 3
    assert events(db, t.id) == ["ipn_received", "risk_hold", "duplicate_ignored"]
    # Then 4
    dup = next(e for e in event_rows(db, t.id) if e.event_type == "duplicate_ignored")
    assert (
        dup.description
        == "Duplicate ipn callback ignored; transaction already RISK_HOLD"
    )
    # Then 5
    row = reread(db, t.id)
    assert row.status == "RISK_HOLD"
    assert row.val_id == "VAL-1"
    assert row.risk_level == 1
    # Then 6
    assert row.validated_at == V0


# [claude] PTS-GC-04
def test_pts_gc_04__redirect_after_success_keeps_outcome(db, gw, mk_t):
    """PTS-GC-04 — a redirect after a verified success keeps the stored outcome and val_id.
    Rules: handle_gateway_callback R2."""
    t = mk_t()
    with at(V0):
        paid(db, gw, t)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(
        db, tran_id=A26, val_id="VAL-2", source="redirect_success"
    )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    assert result.val_id == "VAL-1"
    # Then 2
    assert gw.validate.call_count == 0
    db.rollback()
    # Then 3
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.val_id == "VAL-1"
    assert row.validated_at == V0
    # Then 4
    last = event_rows(db, t.id)[-1]
    assert last.event_type == "duplicate_ignored"
    assert last.description == (
        "Duplicate redirect_success callback ignored; transaction already VALIDATED_SUCCESS"
    )
    # Then 5
    assert len(event_rows(db, t.id)) == 3


# [claude] PTS-GC-05
def test_pts_gc_05__callback_finds_any_workspace(db, gw, w2, u3, mk_t):
    """PTS-GC-05 — a callback finds the transaction in any workspace.
    Rules: handle_gateway_callback R1 (callbacks read across workspaces)."""
    t = mk_t(workspace_id=w2.id, initiated_by=u3.id)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    assert result.id == t.id
    assert result.workspace_id == w2.id
    # Then 2
    assert result.status == "VALIDATED_SUCCESS"
    db.rollback()
    # Then 3
    assert reread(db, t.id).status == "VALIDATED_SUCCESS"
    # Then 4
    evs = event_rows(db, t.id)
    assert len(evs) == 2
    assert all(e.workspace_id == w2.id for e in evs)


# [claude] PTS-GC-06
def test_pts_gc_06__unknown_tran_id_404(db, gw, mk_t, mk_x):
    """PTS-GC-06 — an unknown tran_id: 404 passes unchanged, nothing saved, no gateway call.
    Rules: handle_gateway_callback R4; Errors row 1; TC3."""
    t = mk_t()
    commit_point(db, gw)
    before = counts(db)
    before_t = snap_txn(db, t.id)
    mk_x()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.handle_gateway_callback(db, tran_id=Z26, val_id="VAL-1", source="ipn")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Unknown tran_id: " + Z26
    # Then 4
    assert gw.validate.call_count == 0
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap_txn(db, t.id) == before_t


# [claude] PTS-GC-07
def test_pts_gc_07__raising_validate_rolls_back_received_event(db, gw, mk_t, mk_x):
    """PTS-GC-07 — a raising validate: the received event is rolled back too.
    Rules: handle_gateway_callback R4; Errors row 2; TC3."""
    t = mk_t()
    e = TimeoutError("validate timeout")
    gw.validate.side_effect = e
    commit_point(db, gw)
    before_t = snap_txn(db, t.id)
    mk_x()
    # Then 1
    with pytest.raises(TimeoutError) as exc:
        svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 2
    assert exc.value is e
    # Then 3
    assert gw.validate.call_count == 1
    # Then 4
    assert len(event_rows(db, t.id)) == 0
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert snap_txn(db, t.id) == before_t
    # Then 7
    assert usable(db)


# [claude] PTS-GC-08
def test_pts_gc_08__after_failed_callback_next_processes_normally(db, gw, mk_t):
    """PTS-GC-08 — after a failed callback the next one processes the row normally.
    Rules: handle_gateway_callback R4."""
    t = mk_t()
    commit_point(db, gw)
    gw.validate.side_effect = TimeoutError("t")
    with pytest.raises(TimeoutError):
        svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    gw.validate.side_effect = None
    gw.validate.return_value = OKV(A26)
    gw.reset_mock()
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    assert gw.validate.call_count == 1
    db.rollback()
    # Then 3
    assert events(db, t.id) == ["ipn_received", "validated_success"]


# [claude] PTS-GC-09
def test_pts_gc_09__failing_commit_saves_nothing(db, gw, mk_t):
    """PTS-GC-09 — a failing commit saves nothing and validate is not called again.
    Rules: handle_gateway_callback R5; Errors row 3; TC4."""
    t = mk_t()
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert gw.validate.call_count == 1
    # Then 4
    assert len(event_rows(db, t.id)) == 0
    # Then 5
    row = reread(db, t.id)
    assert row.status == "INITIATED"
    assert row.val_id is None


# [claude] PTS-GC-10
def test_pts_gc_10__failing_refresh_leaves_outcome_saved(db, gw, mk_t):
    """PTS-GC-10 — a failing re-read leaves the outcome saved.
    Rules: handle_gateway_callback R6; TC5."""
    t = mk_t()
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, t.id).status == "VALIDATED_SUCCESS"
    # Then 3
    assert events(db, t.id) == ["ipn_received", "validated_success"]


# [claude] PTS-GC-11
def test_pts_gc_11__row_locked_before_validate(db, gw, mk_t):
    """PTS-GC-11 — the row is locked with FOR UPDATE before validate runs.
    Rules: handle_gateway_callback R3."""
    mk_t()
    commit_point(db, gw)
    seen = []

    def _validate(val_id):
        seen.append(len(stmts))
        return OKV(A26)

    gw.validate.side_effect = _validate
    with recorder(db) as stmts:
        result = svc.handle_gateway_callback(
            db, tran_id=A26, val_id="VAL-1", source="ipn"
        )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    locks = lock_stmts(stmts)
    assert len(locks) == 1
    # Then 3
    assert "SKIP LOCKED" not in locks[0]
    assert "NOWAIT" not in locks[0]
    # Then 4
    assert stmts.index(locks[0]) < seen[0]


# [claude] PTS-GC-12
def test_pts_gc_12__foreign_val_id_rejection_committed(db, gw, mk_t):
    """PTS-GC-12 — a foreign val_id: the rejection is committed and gateway fields stay empty.
    Rules: handle_gateway_callback R1 (rejection path)."""
    t = mk_t()
    gw.validate.return_value = OKV(B26)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-9", source="ipn")
    # Then 1
    assert result.id == t.id
    db.rollback()
    # Then 2
    evs = event_rows(db, t.id)
    assert len(evs) == 2
    assert evs[0].event_type == "ipn_received"
    # Then 3
    assert (
        evs[1].description
        == "val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id="
        + B26
    )
    # Then 4
    row = reread(db, t.id)
    assert row.val_id is None
    assert row.bank_tran_id is None
    assert row.risk_level is None


# [claude] PTS-GC-13
@xbug(BUG_023)
def test_pts_gc_13__foreign_val_id_leaves_initiated(db, gw, mk_t):
    """PTS-GC-13 — pass-through BUG-023: a foreign val_id leaves the row INITIATED.
    Rules: handle_gateway_callback R1 [BUG-023]."""
    t = mk_t()
    gw.validate.return_value = OKV(B26)
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-9", source="ipn")
    # Then 1
    assert result.status == "INITIATED"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "INITIATED"
    assert row.validated_at is None
    # Then 3
    assert events(db, t.id) == ["ipn_received", "validation_rejected"]


# [claude] PTS-GC-14
@xbug(BUG_026)
def test_pts_gc_14__verified_ipn_replaces_unverified_cancel(db, gw, mk_t):
    """PTS-GC-14 — pass-through BUG-026: a verified IPN replaces an unverified cancel.
    Rules: handle_gateway_callback R1 (replacement) [BUG-026]."""
    t = mk_t()
    svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
    )
    commit_point(db, gw)
    result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    assert gw.validate.call_count == 1
    db.rollback()
    # Then 3
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.val_id == "VAL-1"


# [claude] PTS-GC-15
def test_pts_gc_15__404_discards_other_pending_change(db, gw, mk_t):
    """PTS-GC-15 — a 404 discards another pending change; the session stays usable.
    Rules: handle_gateway_callback R4; TC3 (session usable, other pending change discarded)."""
    t = mk_t()
    commit_point(db, gw)
    t.cus_name = "Pending Edit"
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.handle_gateway_callback(
            db, tran_id=Z26, val_id="VAL-1", source="redirect_fail"
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Unknown tran_id: " + Z26
    # Then 3
    assert t not in db.dirty
    # Then 4
    assert reread(db, t.id).cus_name == "Karim"
    # Then 5
    assert usable(db)


# [claude] PTS-GC-16
def test_pts_gc_16__commit_once_after_gateway_call(db, gw, mk_t):
    """PTS-GC-16 — the commit happens once, after the gateway call.
    Rules: handle_gateway_callback R5; TC1."""
    mk_t()
    commit_point(db, gw)
    seen = []

    def _validate(val_id):
        seen.append(cm.call_count)
        return OKV(A26)

    gw.validate.side_effect = _validate
    with spies(db) as (cm, _rb):
        result = svc.handle_gateway_callback(
            db, tran_id=A26, val_id="VAL-1", source="ipn"
        )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    assert seen == [0]
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert gw.validate.call_count == 1


# =========================================================================== #
# handle_terminal_without_validation
# =========================================================================== #


# [claude] PTS-TW-01
def test_pts_tw_01__cancel_on_initiated_committed(db, gw, mk_t):
    """PTS-TW-01 — a cancel redirect on INITIATED is committed.
    Rules: handle_terminal_without_validation R1, R3; TC1, TC2."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
    )
    # Then 1
    unloaded = inspect(result).unloaded
    assert "status" not in unloaded
    assert "validated_at" not in unloaded
    assert "updated_at" not in unloaded
    # Then 2
    assert isinstance(result, PaymentTransaction)
    assert result.id == t.id
    assert result.status == "CANCELLED"
    # Then 3
    assert gw.validate.call_count == 0
    assert gw.init_session.call_count == 0
    assert gw.query_by_tran_id.call_count == 0
    db.rollback()
    # Then 4
    row = reread(db, t.id)
    assert row.status == "CANCELLED"
    assert row.validated_at == NOW
    assert row.val_id is None
    # Then 5
    evs = event_rows(db, t.id)
    assert len(evs) == 1
    assert (
        evs[0].description
        == "Marked CANCELLED via redirect_cancel (no val_id to validate)"
    )
    assert evs[0].performed_by is None
    assert evs[0].metadata_json is None


# [claude] PTS-TW-02
def test_pts_tw_02__fail_redirect_validated_failed(db, gw, mk_t):
    """PTS-TW-02 — a fail redirect without val_id is committed as VALIDATED_FAILED.
    Rules: handle_terminal_without_validation R1."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db,
        tran_id=A26,
        terminal_status="VALIDATED_FAILED",
        source="redirect_fail_no_val_id",
    )
    # Then 1
    assert result.status == "VALIDATED_FAILED"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "VALIDATED_FAILED"
    assert row.validated_at == NOW
    # Then 3
    evs = event_rows(db, t.id)
    assert len(evs) == 1
    assert (
        evs[0].description
        == "Marked VALIDATED_FAILED via redirect_fail_no_val_id (no val_id to validate)"
    )


# [claude] PTS-TW-03
@xbug(BUG_028)
def test_pts_tw_03__cancel_event_type_redirect_cancel(db, gw, mk_t):
    """PTS-TW-03 — pass-through BUG-028: the cancel event type is redirect_cancel.
    Rules: handle_terminal_without_validation R1 [BUG-028]."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
    )
    # Then 1
    assert result.status == "CANCELLED"
    db.rollback()
    # Then 2
    assert events(db, t.id) == ["redirect_cancel"]


# [claude] PTS-TW-04
@xbug(BUG_026)
def test_pts_tw_04__redirect_outcome_stored_unverified(db, gw, mk_t):
    """PTS-TW-04 — pass-through BUG-026: the redirect's outcome is stored unverified.
    Rules: handle_terminal_without_validation R1 [BUG-026]."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
    )
    # Then 1
    assert result.status == "CANCELLED"
    db.rollback()
    # Then 2
    assert reread(db, t.id).outcome_verified is False


# [claude] PTS-TW-05
def test_pts_tw_05__cancel_on_paid_row_duplicate(db, gw, mk_t):
    """PTS-TW-05 — a cancel on a paid row: status stays, one duplicate_ignored committed.
    Rules: handle_terminal_without_validation R2."""
    t = mk_t()
    with at(V0):
        paid(db, gw, t)
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
    )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.validated_at == V0
    assert row.val_id == "VAL-1"
    # Then 3
    assert events(db, t.id) == [
        "ipn_received",
        "validated_success",
        "duplicate_ignored",
    ]
    # Then 4
    dup = next(e for e in event_rows(db, t.id) if e.event_type == "duplicate_ignored")
    assert (
        dup.description
        == "Duplicate redirect_cancel callback ignored; transaction already VALIDATED_SUCCESS"
    )


# [claude] PTS-TW-06
def test_pts_tw_06__second_cancel_is_duplicate(db, gw, mk_t):
    """PTS-TW-06 — a second cancel on an unverified cancel is a duplicate.
    Rules: handle_terminal_without_validation R2."""
    t = mk_t()
    with at(V0):
        svc.handle_terminal_without_validation(
            db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
        )
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db,
        tran_id=A26,
        terminal_status="VALIDATED_FAILED",
        source="redirect_fail_no_val_id",
    )
    # Then 1
    assert result.status == "CANCELLED"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "CANCELLED"
    assert row.validated_at == V0
    # Then 3
    evs = event_rows(db, t.id)
    assert len(evs) == 2
    assert evs[-1].event_type == "duplicate_ignored"
    assert evs[-1].description == (
        "Duplicate redirect_fail_no_val_id callback ignored; transaction already CANCELLED"
    )


# [claude] PTS-TW-07
def test_pts_tw_07__unknown_tran_id_404(db, gw, mk_t, mk_x):
    """PTS-TW-07 — an unknown tran_id: 404 unchanged, nothing saved.
    Rules: handle_terminal_without_validation R4; Errors row 1; TC3."""
    t = mk_t()
    commit_point(db, gw)
    before = counts(db)
    before_t = snap_txn(db, t.id)
    mk_x()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.handle_terminal_without_validation(
            db, tran_id=Z26, terminal_status="CANCELLED", source="redirect_cancel"
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Unknown tran_id: " + Z26
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_txn(db, t.id) == before_t


# [claude] PTS-TW-08
def test_pts_tw_08__terminal_status_20_chars_stored(db, gw, mk_t):
    """PTS-TW-08 — a terminal status of 20 characters is stored.
    Rules: handle_terminal_without_validation R4 (boundary)."""
    t = mk_t()
    commit_point(db, gw)
    result = svc.handle_terminal_without_validation(
        db, tran_id=A26, terminal_status="S" * 20, source="redirect_cancel"
    )
    # Then 1
    assert result.status == "S" * 20
    db.rollback()
    # Then 2
    assert reread(db, t.id).status == "S" * 20


# [claude] PTS-TW-09
def test_pts_tw_09__terminal_status_21_chars_data_error(db, gw, mk_t, mk_x):
    """PTS-TW-09 — a terminal status of 21 characters: DataError, nothing saved.
    Rules: handle_terminal_without_validation R4; Errors row 2; TC3."""
    t = mk_t()
    commit_point(db, gw)
    before_t = snap_txn(db, t.id)
    mk_x()
    # Then 1
    with pytest.raises(DataError):
        svc.handle_terminal_without_validation(
            db, tran_id=A26, terminal_status="S" * 21, source="redirect_cancel"
        )
    # Then 2
    assert len(event_rows(db, t.id)) == 0
    # Then 3
    assert x_count(db) == 0
    # Then 4
    assert snap_txn(db, t.id) == before_t
    # Then 5
    assert usable(db)


# [claude] PTS-TW-10
def test_pts_tw_10__failing_commit_saves_nothing(db, gw, mk_t):
    """PTS-TW-10 — a failing commit saves nothing.
    Rules: handle_terminal_without_validation R4; Errors row 3; TC4."""
    t = mk_t()
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.handle_terminal_without_validation(
                db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(event_rows(db, t.id)) == 0
    # Then 4
    row = reread(db, t.id)
    assert row.status == "INITIATED"
    assert row.validated_at is None


# [claude] PTS-TW-11
def test_pts_tw_11__failing_refresh_leaves_outcome_saved(db, gw, mk_t):
    """PTS-TW-11 — a failing re-read leaves the outcome saved.
    Rules: handle_terminal_without_validation R4; TC5."""
    t = mk_t()
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.handle_terminal_without_validation(
                db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, t.id).status == "CANCELLED"
    # Then 3
    assert len(event_rows(db, t.id)) == 1


# [claude] PTS-TW-12
def test_pts_tw_12__row_locked_no_gateway_call(db, gw, mk_t):
    """PTS-TW-12 — the row is locked with FOR UPDATE and no gateway call is made.
    Rules: handle_terminal_without_validation R3."""
    mk_t()
    commit_point(db, gw)
    with recorder(db) as stmts:
        result = svc.handle_terminal_without_validation(
            db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel"
        )
    # Then 1
    assert result.status == "CANCELLED"
    # Then 2
    locks = lock_stmts(stmts)
    assert len(locks) == 1
    # Then 3
    assert "SKIP LOCKED" not in locks[0]
    assert "NOWAIT" not in locks[0]
    # Then 4
    assert gw.validate.call_count == 0


# =========================================================================== #
# resolve_risk
# =========================================================================== #


# [claude] PTS-RR-01
def test_pts_rr_01__approval_committed_no_name(db, gw, w1, u1, mk_t):
    """PTS-RR-01 — an approval is committed; the answer has no initiator name.
    Rules: resolve_risk R1; TC1, TC2."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    result = svc.resolve_risk(
        db,
        transaction_id=t.id,
        workspace_id=w1.id,
        user_id=u1.id,
        approve=True,
        note=NOTE,
    )
    # Then 1
    assert isinstance(result, PaymentTransactionResponse)
    # Then 2
    assert result.id == t.id
    assert result.status == "VALIDATED_SUCCESS"
    # Then 3
    assert result.risk_resolved_by == u1.id
    assert result.risk_resolution_note == NOTE
    # Then 4
    assert result.initiated_by_name is None
    # Then 5
    assert gw.validate.call_count == 0
    db.rollback()
    # Then 6
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.risk_resolved_by == u1.id
    assert row.risk_resolved_at == NOW
    assert row.risk_resolution_note == NOTE
    # Then 7
    assert events(db, t.id) == ["ipn_received", "risk_hold", "risk_resolved"]
    # Then 8
    rr = next(e for e in event_rows(db, t.id) if e.event_type == "risk_resolved")
    assert rr.description == "Risk hold approved: Card holder confirmed by phone"
    assert rr.performed_by == u1.id


# [claude] PTS-RR-02
def test_pts_rr_02__rejection_committed(db, gw, w1, u1, mk_t):
    """PTS-RR-02 — a rejection is committed as VALIDATED_FAILED.
    Rules: resolve_risk R1."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    result = svc.resolve_risk(
        db,
        transaction_id=t.id,
        workspace_id=w1.id,
        user_id=u1.id,
        approve=False,
        note=NOTE,
    )
    # Then 1
    assert result.status == "VALIDATED_FAILED"
    # Then 2
    assert result.initiated_by_name is None
    db.rollback()
    # Then 3
    row = reread(db, t.id)
    assert row.status == "VALIDATED_FAILED"
    assert row.risk_resolution_note == NOTE
    # Then 4
    last = event_rows(db, t.id)[-1]
    assert last.event_type == "risk_resolved"
    assert last.description == "Risk hold rejected: Card holder confirmed by phone"


# [claude] PTS-RR-03
def test_pts_rr_03__second_resolve_400(db, gw, w1, u1, u2, mk_t, mk_x):
    """PTS-RR-03 — a second resolve gets 400; the first decision and its one event stay.
    Rules: resolve_risk R2; Errors row 2; TC3."""
    t = mk_t()
    held(db, gw, t)
    svc.resolve_risk(
        db,
        transaction_id=t.id,
        workspace_id=w1.id,
        user_id=u1.id,
        approve=True,
        note=NOTE,
    )
    commit_point(db, gw)
    before_t = snap_txn(db, t.id)
    mk_x()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resolve_risk(
            db,
            transaction_id=t.id,
            workspace_id=w1.id,
            user_id=u2.id,
            approve=False,
            note="Second thoughts",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Only transactions in RISK_HOLD can be resolved (current status: VALIDATED_SUCCESS)"
    )
    # Then 4
    assert events(db, t.id).count("risk_resolved") == 1
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert snap_txn(db, t.id) == before_t
    # Then 7
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.risk_resolved_by == u1.id
    assert row.risk_resolution_note == NOTE


# [claude] PTS-RR-04
def test_pts_rr_04__resolving_initiated_400(db, gw, w1, u1, mk_t):
    """PTS-RR-04 — resolving an INITIATED row gets 400.
    Rules: resolve_risk R2; Errors row 2."""
    t = mk_t()
    commit_point(db, gw)
    before = counts(db)
    before_t = snap_txn(db, t.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resolve_risk(
            db,
            transaction_id=t.id,
            workspace_id=w1.id,
            user_id=u1.id,
            approve=True,
            note=NOTE,
        )
    assert exc.value.status_code == 400
    # Then 2
    assert (
        exc.value.detail
        == "Only transactions in RISK_HOLD can be resolved (current status: INITIATED)"
    )
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_txn(db, t.id) == before_t


# [claude] PTS-RR-05
def test_pts_rr_05__held_row_of_w2_404_for_w1(db, gw, w1, w2, u1, u3, mk_t):
    """PTS-RR-05 — a held row of W2 is 404 for W1 and stays held.
    Rules: resolve_risk R3; Errors row 1; HR-16."""
    t = mk_t(workspace_id=w2.id, initiated_by=u3.id)
    held(db, gw, t)
    commit_point(db, gw)
    before = counts(db)
    before_t = snap_txn(db, t.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resolve_risk(
            db,
            transaction_id=t.id,
            workspace_id=w1.id,
            user_id=u1.id,
            approve=True,
            note=NOTE,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Payment transaction {t.id} not found"
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_txn(db, t.id) == before_t


# [claude] PTS-RR-06
def test_pts_rr_06__held_row_of_w0_404_for_w1(db, gw, w0, w1, u1, u3, mk_t):
    """PTS-RR-06 — a held row of W0 is 404 for W1 and stays held.
    Rules: resolve_risk R3; HR-16."""
    t = mk_t(workspace_id=w0.id, initiated_by=u3.id)
    held(db, gw, t)
    commit_point(db, gw)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resolve_risk(
            db,
            transaction_id=t.id,
            workspace_id=w1.id,
            user_id=u1.id,
            approve=False,
            note=NOTE,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Payment transaction {t.id} not found"
    # Then 3
    assert counts(db) == before
    # Then 4
    row = reread(db, t.id)
    assert row.status == "RISK_HOLD"
    assert row.risk_resolved_by is None


# [claude] PTS-RR-07
def test_pts_rr_07__unknown_id_404(db, gw, w1, u1, mk_t):
    """PTS-RR-07 — an unknown id gets 404.
    Rules: resolve_risk R3; Errors row 1."""
    mk_t()
    commit_point(db, gw)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resolve_risk(
            db,
            transaction_id=MISSING,
            workspace_id=w1.id,
            user_id=u1.id,
            approve=True,
            note=NOTE,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Payment transaction 999999999 not found"
    # Then 3
    assert counts(db) == before


# [claude] PTS-RR-08
@xbug(BUG_029)
def test_pts_rr_08__read_with_for_update_of(db, gw, w1, u1, mk_t):
    """PTS-RR-08 — BUG-029: the row is read with FOR UPDATE OF payment_transactions.
    Rules: resolve_risk R2a [BUG-029]."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    with recorder(db) as stmts:
        result = svc.resolve_risk(
            db,
            transaction_id=t.id,
            workspace_id=w1.id,
            user_id=u1.id,
            approve=True,
            note=NOTE,
        )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    locks = [s for s in stmts if "FOR UPDATE OF payment_transactions" in s]
    assert len(locks) == 1
    # Then 3
    assert "SKIP LOCKED" not in locks[0]
    assert "NOWAIT" not in locks[0]


# [claude] PTS-RR-09
def test_pts_rr_09__failing_commit_leaves_hold(db, gw, w1, u1, mk_t):
    """PTS-RR-09 — a failing commit leaves the hold in place.
    Rules: resolve_risk R4; Errors row 3; TC4."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.resolve_risk(
                db,
                transaction_id=t.id,
                workspace_id=w1.id,
                user_id=u1.id,
                approve=True,
                note=NOTE,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, t.id)
    assert row.status == "RISK_HOLD"
    assert row.risk_resolved_by is None
    # Then 4
    assert events(db, t.id).count("risk_resolved") == 0


# [claude] PTS-RR-10
def test_pts_rr_10__failing_refresh_leaves_decision(db, gw, w1, u1, mk_t):
    """PTS-RR-10 — a failing re-read leaves the decision saved.
    Rules: resolve_risk R4; TC5."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.resolve_risk(
                db,
                transaction_id=t.id,
                workspace_id=w1.id,
                user_id=u1.id,
                approve=True,
                note=NOTE,
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    row = reread(db, t.id)
    assert row.status == "VALIDATED_SUCCESS"
    assert row.risk_resolution_note == NOTE
    # Then 3
    assert events(db, t.id).count("risk_resolved") == 1


# [claude] PTS-RR-11
@xbug(BUG_3022 + "; " + BUG_019 + "; " + BUG_026)
def test_pts_rr_11__resolve_answer_has_failed_reason_and_verified(db, gw, w1, u1, mk_t):
    """PTS-RR-11 — BUG-3022: the resolve answer carries failed_reason and outcome_verified.
    Rules: resolve_risk R1; _to_response R1a [BUG-3022] (outcome_verified also needs BUG-026)."""
    t = mk_t()
    held(db, gw, t)
    commit_point(db, gw)
    result = svc.resolve_risk(
        db,
        transaction_id=t.id,
        workspace_id=w1.id,
        user_id=u1.id,
        approve=True,
        note=NOTE,
    )
    # Then 1
    assert result.status == "VALIDATED_SUCCESS"
    # Then 2
    assert result.failed_reason is None
    # Then 3
    assert result.outcome_verified is True


# =========================================================================== #
# get_transaction_by_tran_id
# =========================================================================== #


# [claude] PTS-D-01
def test_pts_d_01__transaction_with_name_and_events(db, gw, w1, u1, mk_t):
    """PTS-D-01 — a transaction of the workspace with its name and events.
    Rules: get_transaction_by_tran_id R1, R4."""
    t = mk_t()
    e1 = ev(db, t, "initiated", datetime(2026, 9, 27, 9, 0))
    e2 = ev(
        db,
        t,
        "ipn_received",
        datetime(2026, 9, 27, 9, 5),
        performed_by=u1.id,
        metadata_json={"k": "v"},
    )
    commit_point(db, gw)
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, PaymentTransactionDetailResponse)
    # Then 2
    assert result.id == t.id
    assert result.tran_id == A26
    assert result.status == "INITIATED"
    assert result.amount == Decimal("500.00")
    # Then 3
    assert result.initiated_by_name == "Karim"
    # Then 4
    assert [e.id for e in result.events] == [e1.id, e2.id]
    # Then 5
    assert isinstance(result.events[1], PaymentTransactionEventResponse)
    # Then 6
    assert result.events[1].payment_transaction_id == t.id
    assert result.events[1].event_type == "ipn_received"
    assert result.events[1].description == "ipn_received note"
    assert result.events[1].metadata_json == {"k": "v"}
    assert result.events[1].performed_by == u1.id
    assert result.events[1].created_at == datetime(2026, 9, 27, 9, 5)
    # Then 7
    assert not hasattr(result.events[0], "workspace_id")


# [claude] PTS-D-02
def test_pts_d_02__no_initiator_name_none(db, w1, mk_t):
    """PTS-D-02 — no initiator: the name is None.
    Rules: get_transaction_by_tran_id R1."""
    t = mk_t(initiated_by=None)
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert result.initiated_by_name is None
    # Then 3
    assert result.events == []


# [claude] PTS-D-03
def test_pts_d_03__tran_id_of_w2_404_for_w1(db, w1, w2, u3, mk_t):
    """PTS-D-03 — a tran_id of W2 is 404 for W1.
    Rules: get_transaction_by_tran_id R2; Errors row 1; HR-16."""
    mk_t(workspace_id=w2.id, initiated_by=u3.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Payment transaction " + A26 + " not found"


# [claude] PTS-D-04
def test_pts_d_04__tran_id_of_w0_404_for_w1(db, w0, w1, u3, mk_t):
    """PTS-D-04 — a tran_id of W0 is 404 for W1.
    Rules: get_transaction_by_tran_id R2; HR-16."""
    mk_t(workspace_id=w0.id, initiated_by=u3.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Payment transaction " + A26 + " not found"


# [claude] PTS-D-05 … PTS-D-09 (identical setup and checks, one tran_id each)
@pytest.mark.parametrize(
    "sent",
    [
        pytest.param("nope", id="PTS-D-05"),
        pytest.param("A" * 26, id="PTS-D-06"),
        pytest.param(A26 + " ", id="PTS-D-07"),
        pytest.param("a" * 25, id="PTS-D-08"),
        pytest.param("", id="PTS-D-09"),
    ],
)
def test_pts_d_05_09__not_exact_tran_id_404(db, w1, mk_t, sent):
    """PTS-D-05 … PTS-D-09 — an unknown tran_id, the tran_id in capitals, with a trailing space,
    a part of it, or "" is 404 with the requested id in the message.
    Rules: get_transaction_by_tran_id R2, R3."""
    mk_t()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_transaction_by_tran_id(db, tran_id=sent, workspace_id=w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Payment transaction " + sent + " not found"


# [claude] PTS-D-10
def test_pts_d_10__101_events_all_oldest_first(db, w1, mk_t):
    """PTS-D-10 — 101 events are all returned, oldest first.
    Rules: get_transaction_by_tran_id R4 (no cap), R5."""
    t = mk_t()
    base = datetime(2026, 9, 1)
    for k in range(100, -1, -1):
        ev(db, t, "note", base + timedelta(minutes=k))
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert len(result.events) == 101
    # Then 2
    assert [e.created_at for e in result.events] == [
        base + timedelta(minutes=k) for k in range(101)
    ]


# [claude] PTS-D-11
@xbug(BUG_1191)
def test_pts_d_11__event_of_w2_not_listed(db, w1, w2, mk_t):
    """PTS-D-11 — BUG-1191: an event of W2 on W1's transaction is not listed.
    Rules: get_transaction_by_tran_id R4a [BUG-1191]; HR-16."""
    t = mk_t()
    e1 = ev(db, t, "initiated", datetime(2026, 9, 27, 9, 0))
    ev(
        db,
        t,
        "note",
        datetime(2026, 9, 27, 9, 1),
        workspace_id=w2.id,
        metadata_json={"secret": "w2"},
    )
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert [e.id for e in result.events] == [e1.id]


# [claude] PTS-D-12
@xbug(BUG_1191)
def test_pts_d_12__event_of_w0_not_listed(db, w0, w1, mk_t):
    """PTS-D-12 — BUG-1191: an event of W0 on W1's transaction is not listed.
    Rules: get_transaction_by_tran_id R4a [BUG-1191]; HR-16."""
    t = mk_t()
    ev(db, t, "note", datetime(2026, 9, 27, 8, 0), workspace_id=w0.id)
    e1 = ev(db, t, "initiated", datetime(2026, 9, 27, 9, 0))
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert [e.id for e in result.events] == [e1.id]


# [claude] PTS-D-13
@xbug(BUG_1190)
def test_pts_d_13__event_read_orders_ties_by_id(db, w1, mk_t):
    """PTS-D-13 — BUG-1190: the event read orders ties by id.
    Rules: get_transaction_by_tran_id R5 [BUG-1190]."""
    t = mk_t()
    ev(db, t, "a", datetime(2026, 9, 27, 9, 0))
    with recorder(db) as stmts:
        result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert len(result.events) == 1
    # Then 2
    ev_stmts = [s for s in stmts if selects_events(s)]
    assert len(ev_stmts) == 1
    assert "payment_transaction_events.id" in order_by_part(ev_stmts[0])


# [claude] PTS-D-14
@xbug(BUG_1190, strict=False)
def test_pts_d_14__tied_events_lower_id_first(db, w1, mk_t):
    """PTS-D-14 — BUG-1190: tied events come back lower id first.
    Rules: get_transaction_by_tran_id R5 [BUG-1190]."""
    t = mk_t()
    e1 = ev(db, t, "a", datetime(2026, 9, 27, 9, 0))
    e2 = ev(db, t, "b", datetime(2026, 9, 27, 9, 0))
    e1.description = "edited"
    db.flush()
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert len(result.events) == 2
    # Then 2
    assert [e.id for e in result.events] == [e1.id, e2.id]


# [claude] PTS-D-15
def test_pts_d_15__read_404_no_commit_no_lock_pending_stays(db, gw, w1, mk_t):
    """PTS-D-15 — a read: no commit, no rollback, no lock, a pending edit stays (also on 404).
    Rules: get_transaction_by_tran_id R6; TC6."""
    mk_t()
    b = mk_t(tran_id=B26)
    commit_point(db, gw)
    b.cus_name = "Pending Edit"
    with spies(db) as (cm, rb), recorder(db) as stmts:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.get_transaction_by_tran_id(db, tran_id=Z26, workspace_id=w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert cm.call_count == 0
    assert rb.call_count == 0
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not [s for s in stmts if "FOR UPDATE" in s]


# [claude] PTS-D-16
def test_pts_d_16__read_success_no_lock_pending_stays(db, gw, w1, mk_t):
    """PTS-D-16 — the detail read also succeeds without a lock.
    Rules: get_transaction_by_tran_id R6; TC6."""
    t = mk_t()
    b = mk_t(tran_id=B26)
    commit_point(db, gw)
    b.cus_name = "Pending Edit"
    with spies(db) as (cm, rb), recorder(db) as stmts:
        result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert cm.call_count == 0
    assert rb.call_count == 0
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not [s for s in stmts if "FOR UPDATE" in s]


# [claude] PTS-D-17
@xbug(BUG_3022 + "; " + BUG_019 + "; " + BUG_026)
def test_pts_d_17__detail_has_failed_reason_and_verified(db, w1, mk_t):
    """PTS-D-17 — BUG-3022: the detail answer carries failed_reason and outcome_verified.
    Rules: get_transaction_by_tran_id R1; _to_response R1a [BUG-3022]."""
    t = mk_t()
    result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert result.failed_reason is None
    # Then 3
    assert result.outcome_verified is False


# =========================================================================== #
# list_transactions
# =========================================================================== #


# [claude] PTS-L-01
def test_pts_l_01__only_w1_rows_with_names(db, w0, w1, w2, u3, mk_t):
    """PTS-L-01 — only W1's rows, every status, as responses with names.
    Rules: list_transactions R1, R3."""
    mk_t(workspace_id=w0.id, tran_id="0" * 26, initiated_by=u3.id)
    a = mk_t()
    b = mk_t(tran_id=B26, status="INIT_FAILED")
    c = mk_t(tran_id=C26, status="VALIDATED_SUCCESS", initiated_by=None)
    mk_t(workspace_id=w2.id, tran_id="9" * 26, initiated_by=u3.id)
    result = svc.list_transactions(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert all(isinstance(item, PaymentTransactionResponse) for item in result)
    # Then 2
    assert {r.id for r in result} == {a.id, b.id, c.id}
    # Then 3
    assert next(r for r in result if r.id == a.id).initiated_by_name == "Karim"
    # Then 4
    assert next(r for r in result if r.id == c.id).initiated_by_name is None


# [claude] PTS-L-02
def test_pts_l_02__workspace_without_rows_empty(db, w1, w2, u3, mk_t):
    """PTS-L-02 — a workspace with no rows gets [].
    Rules: list_transactions R1."""
    mk_t(workspace_id=w2.id, initiated_by=u3.id)
    result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert result == []


# [claude] PTS-L-03
def test_pts_l_03__newest_created_at_first(db, w1, mk_t):
    """PTS-L-03 — newest created_at first, even when ids rise the other way.
    Rules: list_transactions R2."""
    a = mk_t(created_at=datetime(2026, 9, 3))
    b = mk_t(tran_id=B26, created_at=datetime(2026, 9, 1))
    c = mk_t(tran_id=C26, created_at=datetime(2026, 9, 2))
    result = svc.list_transactions(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert [r.id for r in result] == [a.id, c.id, b.id]


# [claude] PTS-L-04
def test_pts_l_04__skip_and_limit_page(db, w1, mk_t):
    """PTS-L-04 — skip and limit page the ordered list.
    Rules: list_transactions R2."""
    for k in range(1, 6):
        mk_t(tran_id=str(k) * 26, created_at=datetime(2026, 9, k))
    result = svc.list_transactions(db, workspace_id=w1.id, skip=1, limit=2)
    # Then 1
    assert [r.tran_id for r in result] == ["4" * 26, "3" * 26]


# [claude] PTS-L-05
def test_pts_l_05__default_limit_100(db, w1, mk_t):
    """PTS-L-05 — the default limit is 100.
    Rules: list_transactions R2 (default limit=100)."""
    base = datetime(2026, 9, 1)
    for k in range(101):
        mk_t(tran_id=f"{k:026x}", created_at=base + timedelta(minutes=k))
    result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].tran_id == f"{100:026x}"
    # Then 3
    assert f"{0:026x}" not in {r.tran_id for r in result}


# [claude] PTS-L-06
def test_pts_l_06__limit_0_empty(db, w1, mk_t):
    """PTS-L-06 — limit=0 gives [].
    Rules: list_transactions R2."""
    mk_t()
    result = svc.list_transactions(db, workspace_id=w1.id, limit=0)
    # Then 1
    assert result == []


# [claude] PTS-L-07
def test_pts_l_07__limit_1_newest_only(db, w1, mk_t):
    """PTS-L-07 — limit=1 gives the newest row only.
    Rules: list_transactions R2."""
    mk_t(created_at=datetime(2026, 9, 1))
    b = mk_t(tran_id=B26, created_at=datetime(2026, 9, 2))
    result = svc.list_transactions(db, workspace_id=w1.id, limit=1)
    # Then 1
    assert [r.id for r in result] == [b.id]


# [claude] PTS-L-08
def test_pts_l_08__workspace_filter_before_paging(db, w0, w1, w2, u3, mk_t):
    """PTS-L-08 — the workspace filter runs before paging.
    Rules: list_transactions R1, R2 (HR-5)."""
    mk_t(
        workspace_id=w0.id,
        tran_id="0" * 26,
        initiated_by=u3.id,
        created_at=datetime(2026, 9, 9),
    )
    a = mk_t(created_at=datetime(2026, 9, 1))
    mk_t(tran_id=B26, created_at=datetime(2026, 9, 2))
    mk_t(
        workspace_id=w2.id,
        tran_id="9" * 26,
        initiated_by=u3.id,
        created_at=datetime(2026, 9, 8),
    )
    result = svc.list_transactions(db, workspace_id=w1.id, skip=1, limit=1)
    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] PTS-L-09
def test_pts_l_09__negative_skip_data_error_no_rollback(db, w1, mk_t):
    """PTS-L-09 — a negative skip reaches the database as DataError, and the session is not rolled back.
    Rules: list_transactions Errors (negative skip); R4; TC6."""
    mk_t()
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(DataError):
            with db.begin_nested():
                svc.list_transactions(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert cm.call_count == 0
    assert rb.call_count == 0


# [claude] PTS-L-10
@xbug(BUG_2402)
def test_pts_l_10__list_orders_ties_by_id_desc(db, w1, mk_t):
    """PTS-L-10 — BUG-2402: the list orders ties by id descending.
    Rules: list_transactions R2 [BUG-2402]."""
    mk_t()
    with recorder(db) as stmts:
        result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    pt = [s for s in stmts if selects_pt(s)]
    assert len(pt) == 1
    assert "payment_transactions.id DESC" in order_by_part(pt[0])


# [claude] PTS-L-11
@xbug(BUG_2402, strict=False)
def test_pts_l_11__tied_rows_higher_id_first(db, w1, mk_t):
    """PTS-L-11 — BUG-2402: tied rows come back higher id first.
    Rules: list_transactions R2 [BUG-2402]."""
    a = mk_t(created_at=datetime(2026, 9, 1))
    b = mk_t(tran_id=B26, created_at=datetime(2026, 9, 1))
    result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [r.id for r in result] == [b.id, a.id]


# [claude] PTS-L-12
def test_pts_l_12__read_no_commit_no_lock_pending_stays(db, gw, w1, mk_t):
    """PTS-L-12 — a read: no commit, no rollback, no lock, a pending edit stays.
    Rules: list_transactions R4; TC6."""
    mk_t()
    b = mk_t(tran_id=B26)
    commit_point(db, gw)
    b.cus_name = "Pending Edit"
    with spies(db) as (cm, rb), recorder(db) as stmts:
        result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    assert rb.call_count == 0
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not [s for s in stmts if "FOR UPDATE" in s]


# [claude] PTS-L-13
@xbug(BUG_3022 + "; " + BUG_019 + "; " + BUG_026)
def test_pts_l_13__list_items_have_failed_reason_and_verified(db, w1, mk_t):
    """PTS-L-13 — BUG-3022: list items carry failed_reason and outcome_verified.
    Rules: list_transactions R1; _to_response R1a [BUG-3022]."""
    t = mk_t()
    result = svc.list_transactions(db, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result] == [t.id]
    # Then 2
    assert result[0].failed_reason is None
    # Then 3
    assert result[0].outcome_verified is False
