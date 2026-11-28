"""Unit tests for app/services/waitlist_service.py.

Implements tests/unit/services/waitlist_service.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture): a `commit()` only releases a
savepoint, so the service's commits are safe and the fixture's outer rollback
discards everything. Nothing is patched except what Conventions name: the
settings (salt pepper, key set / no key, `SECRET_KEY`), the Turnstile stub, the
failing commit wrap and the race simulation of WSV-S-06.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (A -> a);
`# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, PendingRollbackError

from app.core.config import settings
from app.dao.waitlist import waitlist_dao
from app.models.waitlist_signup import WaitlistSignup
from app.schemas.waitlist import WaitlistSignupItem, WaitlistSignupRequest
from app.services.waitlist_service import (
    SUCCESS_MESSAGE,
    TURNSTILE_VERIFY_URL,
    hash_client_ip,
    normalize_waitlist_email,
    waitlist_service,
)

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton waitlist_service"
svc = waitlist_service

IP = "203.0.113.7"
T1 = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc)

H_PEPPER = "e0dc27fa1b25a23ba014e36d2a1f1f84450214ba108029b8c207dfaeb0e046f4"
H_SEKRIT = "1fce02c50e4d38a3e4015d6ff683713903f589a12a67afffe499b5814f841882"

# Convention "HTTP500" and "TIMEOUT"
HTTP500 = httpx.HTTPStatusError(
    "500",
    request=httpx.Request("POST", TURNSTILE_VERIFY_URL),
    response=httpx.Response(500, request=httpx.Request("POST", TURNSTILE_VERIFY_URL)),
)
TIMEOUT = httpx.ConnectTimeout("timed out")


# Convention "TAG": once per test
@pytest.fixture
def tag():
    return uuid.uuid4().hex[:10]


# --------------------------------------------------------------------------- #
# Conventions -> externals
# --------------------------------------------------------------------------- #

# Convention "salt pepper"
@pytest.fixture
def salt_pepper():
    with patch.object(settings, "WAITLIST_IP_HASH_SALT", "pepper"):
        yield


# Convention "key set"
@pytest.fixture
def key_set():
    with patch.object(settings, "TURNSTILE_SECRET_KEY", "sk-test"):
        yield


# Convention "no key"
@pytest.fixture
def no_key():
    with patch.object(settings, "TURNSTILE_SECRET_KEY", ""):
        yield


_NO_JSON_ERROR = object()


# Convention "stub(...)": returns the list `posts`, empty before the When
@pytest.fixture
def stub():
    started = []

    def _stub(body=None, status_error=None, json_error=None, post_error=None):
        posts = []

        class _Response:
            def raise_for_status(self):
                if status_error is not None:
                    raise status_error

            def json(self):
                if json_error is not None:
                    raise json_error
                return body

        class Stub:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, data=None, **kw):
                posts.append((url, data))
                if post_error is not None:
                    raise post_error
                return _Response()

        p = patch("app.services.waitlist_service.httpx.AsyncClient", Stub)
        p.start()
        started.append(p)
        return posts

    yield _stub
    for p in started:
        p.stop()


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "signup"
def mk_signup(db, email, **but):
    fields = {
        "email": email, "first_name": "Zed", "last_name": "Ray", "company_name": "Acme",
        "source": "hero", "ip_hash": "h1",
    }
    fields.update(but)
    row = WaitlistSignup(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "req"
def req(email, **but):
    fields = {
        "first_name": "Ann", "last_name": "Lee", "company_name": "Acme", "email": email,
        "wants_product_updates": False, "turnstile_token": "tok-1",
    }
    fields.update(but)
    return WaitlistSignupRequest(**fields)


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

# Convention "row(e)"
def row(db, email):
    db.expire_all()
    return db.execute(select(WaitlistSignup).where(WaitlistSignup.email == email)).scalar_one_or_none()


# Convention "count(e)"
def count(db, email):
    db.expire_all()
    return db.execute(
        select(func.count()).select_from(WaitlistSignup).where(WaitlistSignup.email == email)
    ).scalar_one()


# Convention "re-read X"
def reread(db, signup_id):
    db.expire_all()
    return db.execute(select(WaitlistSignup).where(WaitlistSignup.id == signup_id)).scalar_one_or_none()


def _columns(db, signup_id):
    table = WaitlistSignup.__table__
    found = db.execute(select(table).where(table.c.id == signup_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, signup_id):
    return _columns(db, signup_id)


# ... and after a re-read
def snap(db, signup_id):
    db.expire_all()
    return _columns(db, signup_id)


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "ids(x)" (order is part of the check)
def ids(rows):
    return [r.id for r in rows]


# --------------------------------------------------------------------------- #
# normalize_waitlist_email
# --------------------------------------------------------------------------- #

# [claude] WSV-N-01
def test_wsv_n_01__the_email_is_trimmed_and_lower_cased():
    """WSV-N-01 — the email is trimmed and lower-cased.
    Rules: `normalize_waitlist_email` R1"""
    result = normalize_waitlist_email("  A@B.C ")

    # Then 1
    assert result == "a@b.c"


# --------------------------------------------------------------------------- #
# hash_client_ip
# --------------------------------------------------------------------------- #

# [claude] WSV-H-01
def test_wsv_h_01__none_gives_none(salt_pepper):
    """WSV-H-01 — None gives None.
    Rules: `hash_client_ip` R1"""
    result = hash_client_ip(None)

    # Then 1
    assert result is None


# [claude] WSV-H-02
def test_wsv_h_02__an_empty_text_gives_none(salt_pepper):
    """WSV-H-02 — an empty text gives None.
    Rules: `hash_client_ip` R1"""
    result = hash_client_ip("")

    # Then 1
    assert result is None


# [claude] WSV-H-03
def test_wsv_h_03__an_ip_is_hashed_with_the_salt(salt_pepper):
    """WSV-H-03 — an IP is hashed with the salt.
    Rules: `hash_client_ip` R2"""
    with patch.object(settings, "SECRET_KEY", "sekrit"):
        result = hash_client_ip("203.0.113.7")

    # Then 1
    assert result == H_PEPPER
    # Then 2
    assert len(result) == 64


# [claude] WSV-H-04
def test_wsv_h_04__with_an_empty_salt_the_secret_key_is_the_salt():
    """WSV-H-04 — with an empty salt the secret key is the salt.
    Rules: `hash_client_ip` R2"""
    with patch.object(settings, "WAITLIST_IP_HASH_SALT", ""), patch.object(settings, "SECRET_KEY", "sekrit"):
        result = hash_client_ip("203.0.113.7")

    # Then 1
    assert result == H_SEKRIT


# --------------------------------------------------------------------------- #
# WaitlistService.verify_turnstile
# --------------------------------------------------------------------------- #

# [claude] WSV-T-01
def test_wsv_t_01__without_a_key_nothing_is_checked_and_nothing_is_sent(no_key, stub):
    """WSV-T-01 — without a key nothing is checked and nothing is sent.
    Rules: `verify_turnstile` R1"""
    posts = stub(body={"success": False})
    result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))

    # Then 1
    assert result is None
    # Then 2
    assert posts == []


# [claude] WSV-T-02
def test_wsv_t_02__a_confirmed_token_passes_the_request_carries_secret_token_and_ip(key_set, stub):
    """WSV-T-02 — a confirmed token passes; the request carries secret, token and IP.
    Rules: `verify_turnstile` R2, R3, Returns"""
    posts = stub(body={"success": True})
    result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))

    # Then 1
    assert result is None
    # Then 2
    assert len(posts) == 1
    # Then 3
    assert posts[0][0] == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    # Then 4
    assert posts[0][1] == {"secret": "sk-test", "response": "tok-1", "remoteip": "203.0.113.7"}


# [claude] WSV-T-03
def test_wsv_t_03__an_empty_ip_is_not_sent(key_set, stub):
    """WSV-T-03 — an empty IP is not sent.
    Rules: `verify_turnstile` R2"""
    posts = stub(body={"success": True})
    result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=""))

    # Then 1
    assert result is None
    # Then 2
    assert posts[0][1] == {"secret": "sk-test", "response": "tok-1"}


# [claude] WSV-T-04
def test_wsv_t_04__success_false_is_refused_with_400(key_set, stub):
    """WSV-T-04 — success false is refused with 400.
    Rules: `verify_turnstile` R4, Errors row 1"""
    stub(body={"success": False})
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Verification failed — please try again"


# [claude] WSV-T-05
def test_wsv_t_05__an_answer_without_success_is_refused_with_400(key_set, stub):
    """WSV-T-05 — an answer without success is refused with 400.
    Rules: `verify_turnstile` R4, Errors row 1"""
    stub(body={"error-codes": []})
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Verification failed — please try again"


# [claude] WSV-T-06
def test_wsv_t_06__an_http_error_status_becomes_502(key_set, stub):
    """WSV-T-06 — an HTTP error status becomes 502.
    Rules: `verify_turnstile` R5, Errors row 2"""
    stub(body={"success": True}, status_error=HTTP500)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 502
    # Then 3
    assert exc.value.detail == "Could not verify submission"


# [claude] WSV-T-07
def test_wsv_t_07__a_connect_timeout_becomes_502(key_set, stub):
    """WSV-T-07 — a connect timeout becomes 502.
    Rules: `verify_turnstile` R5, Errors row 2"""
    stub(post_error=TIMEOUT)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 502
    # Then 3
    assert exc.value.detail == "Could not verify submission"


# [claude] WSV-T-08
@pytest.mark.xfail(strict=True, reason="BUG-1580: An unreadable answer from Turnstile is an internal error")
def test_wsv_t_08__an_answer_that_is_not_json_becomes_502(key_set, stub):
    """WSV-T-08 — an answer that is not JSON becomes 502.
    Rules: `verify_turnstile` R5 [BUG-1580], Errors row 2"""
    stub(json_error=ValueError("Expecting value"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 502
    # Then 3
    assert exc.value.detail == "Could not verify submission"


# [claude] WSV-T-09
@pytest.mark.xfail(strict=True, reason="BUG-1580: An unreadable answer from Turnstile is an internal error")
def test_wsv_t_09__a_json_list_becomes_502(key_set, stub):
    """WSV-T-09 — a JSON list becomes 502.
    Rules: `verify_turnstile` R5 [BUG-1580], Errors row 2"""
    stub(body=[1])
    # Then 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))
    # Then 2
    assert exc.value.status_code == 502
    # Then 3
    assert exc.value.detail == "Could not verify submission"


# --------------------------------------------------------------------------- #
# WaitlistService.submit_signup
# --------------------------------------------------------------------------- #

# [claude] WSV-S-01
def test_wsv_s_01__a_new_signup_is_stored_normalised_and_committed(db, tag, salt_pepper):
    """WSV-S-01 — a new signup is stored normalised and committed.
    Rules: `submit_signup` R2, R3, Returns"""
    data = req(
        f"Ann.{tag}@X.com", first_name=" Ann ", last_name=" Lee ", company_name=" Acme ",
        wants_product_updates=True, source="pricing",
    )
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip="203.0.113.7")

    # Then 1
    assert result.ok is True
    # Then 2
    assert result.message == "You're on the list — we'll be in touch."
    # Then 3
    db.rollback()
    assert count(db, f"ann.{tag}@x.com") == 1
    # Then 4
    found = row(db, f"ann.{tag}@x.com")
    assert found.first_name == "Ann"
    assert found.last_name == "Lee"
    assert found.company_name == "Acme"
    # Then 5
    found = row(db, f"ann.{tag}@x.com")
    assert found.wants_product_updates is True
    assert found.source == "pricing"
    assert found.status == "PENDING"
    # Then 6
    found = row(db, f"ann.{tag}@x.com")
    assert found.ip_hash == H_PEPPER


# [claude] WSV-S-02
def test_wsv_s_02__a_blank_company_a_null_source_and_no_ip_are_stored_as_null(db, tag, salt_pepper):
    """WSV-S-02 — a blank company, a null source and no IP are stored as NULL.
    Rules: `submit_signup` R3"""
    data = req(f"bo.{tag}@x.com", company_name="   ", source=None)
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip=None)

    # Then 1
    assert result.ok is True
    # Then 2
    db.rollback()
    found = row(db, f"bo.{tag}@x.com")
    assert found.company_name is None
    assert found.source is None
    assert found.ip_hash is None


# [claude] WSV-S-03
def test_wsv_s_03__a_filled_honeypot_answers_success_and_stores_nothing(db, tag, salt_pepper):
    """WSV-S-03 — a filled honeypot answers success and stores nothing.
    Rules: `submit_signup` R1"""
    data = req(f"bot.{tag}@x.com", website="http://spam.example")
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip=IP)

    # Then 1
    assert result.ok is True
    # Then 2
    assert result.message == SUCCESS_MESSAGE
    # Then 3
    assert count(db, f"bot.{tag}@x.com") == 0


# [claude] WSV-S-04
def test_wsv_s_04__an_empty_honeypot_is_not_caught(db, tag, salt_pepper):
    """WSV-S-04 — an empty honeypot is not caught.
    Rules: `submit_signup` R1"""
    data = req(f"cy.{tag}@x.com", website="")
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip=IP)

    # Then 1
    assert result.ok is True
    # Then 2
    db.rollback()
    assert count(db, f"cy.{tag}@x.com") == 1


# [claude] WSV-S-05
def test_wsv_s_05__an_email_already_on_the_list_in_other_capitals_changes_nothing(db, tag, salt_pepper):
    """WSV-S-05 — an email already on the list, in other capitals, changes nothing.
    Rules: `submit_signup` R2, R6"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    data = req(f"ANN.{tag}@x.com", first_name="Bob", wants_product_updates=True)
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip=IP)

    # Then 1
    assert result.ok is True
    # Then 2
    assert result.message == SUCCESS_MESSAGE
    # Then 3
    db.rollback()
    assert count(db, f"ann.{tag}@x.com") == 1
    # Then 4
    found = reread(db, a.id)
    assert found.first_name == "Zed"
    assert found.wants_product_updates is False
    assert found.ip_hash == "h1"


# [claude] WSV-S-06
def test_wsv_s_06__a_signup_that_loses_the_race_answers_success_pending_changes_are_discarded(
    db, tag, salt_pepper,
):
    """WSV-S-06 — a signup that loses the race answers success; pending changes are discarded.
    Rules: `submit_signup` R7"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    commit_point(db)
    mk_signup(db, f"extra.{tag}@x.com")
    data = req(f"ann.{tag}@x.com", first_name="Bob")

    # Race simulation: the first lookup answers None, every later one is real
    real = waitlist_dao.get_by_email
    calls = []

    def first_none(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            return None
        return real(*a, **kw)

    with patch.object(waitlist_dao, "get_by_email", side_effect=first_none):
        result = svc.submit_signup(db, payload=data, remote_ip=IP)

    # Then 1
    assert result.ok is True
    # Then 2
    assert result.message == SUCCESS_MESSAGE
    # Then 3
    assert count(db, f"extra.{tag}@x.com") == 0
    # Then 4
    assert count(db, f"ann.{tag}@x.com") == 1
    # Then 5
    assert reread(db, a.id).first_name == "Zed"
    # Then 6
    assert usable(db)


# [claude] WSV-S-07
def test_wsv_s_07__a_failing_commit_with_a_new_email_is_rolled_back_and_re_raised(db, tag, salt_pepper):
    """WSV-S-07 — a failing commit with a new email is rolled back and re-raised.
    Rules: `submit_signup` R7, R8; TC4"""
    data = req(f"dee.{tag}@x.com")
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.submit_signup(db, payload=data, remote_ip=IP)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count(db, f"dee.{tag}@x.com") == 0


# [claude] WSV-S-08
def test_wsv_s_08__skip_turnstile_true_changes_nothing(db, tag, salt_pepper):
    """WSV-S-08 — skip_turnstile=True changes nothing.
    Rules: `submit_signup` R5"""
    data = req(f"eve.{tag}@x.com")
    commit_point(db)
    result = svc.submit_signup(db, payload=data, remote_ip=IP, skip_turnstile=True)

    # Then 1
    assert result.ok is True
    # Then 2
    db.rollback()
    found = row(db, f"eve.{tag}@x.com")
    assert found.first_name == "Ann"
    assert found.status == "PENDING"


# [claude] WSV-S-09
@pytest.mark.xfail(strict=True, reason="BUG-1579: Waitlist names of only spaces are accepted and stored empty")
def test_wsv_s_09__a_first_name_of_only_spaces_is_refused_by_the_schema(db, tag, salt_pepper):
    """WSV-S-09 — a first name of only spaces is refused by the schema.
    Rules: `submit_signup` R4 [BUG-1579]"""
    # Then 1
    with pytest.raises(PydanticValidationError):
        WaitlistSignupRequest(first_name="   ", last_name="Lee", email=f"fay.{tag}@x.com", turnstile_token="tok-1")
    # Then 2
    assert count(db, f"fay.{tag}@x.com") == 0


# --------------------------------------------------------------------------- #
# WaitlistService.update_status
# --------------------------------------------------------------------------- #

# [claude] WSV-U-01
def test_wsv_u_01__an_unknown_id_is_answered_with_404(db, tag):
    """WSV-U-01 — an unknown id is answered with 404.
    Rules: `update_status` R1, Errors"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    commit_point(db)
    before = snap_before(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, signup_id=999999999, status_value="CONTACTED")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Waitlist signup not found"
    # Then 4
    assert snap(db, a.id) == before


# [claude] WSV-U-02
def test_wsv_u_02__the_status_is_set_committed_and_returned_as_an_item(db, tag):
    """WSV-U-02 — the status is set, committed and returned as an item.
    Rules: `update_status` R2, Returns"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    commit_point(db)
    result = svc.update_status(db, signup_id=a.id, status_value="CONTACTED")

    # Then 1
    assert isinstance(result, WaitlistSignupItem)
    # Then 2
    assert result.id == a.id
    assert result.status == "CONTACTED"
    assert result.email == f"ann.{tag}@x.com"
    # Then 3
    db.rollback()
    assert reread(db, a.id).status == "CONTACTED"
    # Then 4
    found = reread(db, a.id)
    assert found.first_name == "Zed"
    assert found.wants_product_updates is False
    assert found.ip_hash == "h1"


# [claude] WSV-U-03
def test_wsv_u_03__a_stored_status_outside_the_four_can_be_set_to_one_of_them(db, tag):
    """WSV-U-03 — a stored status outside the four can be set to one of them.
    Rules: `update_status` R2"""
    a = mk_signup(db, f"ann.{tag}@x.com", status="legacy")
    commit_point(db)
    result = svc.update_status(db, signup_id=a.id, status_value="ACCEPTED")

    # Then 1
    assert result.status == "ACCEPTED"
    # Then 2
    db.rollback()
    assert reread(db, a.id).status == "ACCEPTED"


# [claude] WSV-U-04
def test_wsv_u_04__a_failing_commit_is_rolled_back_and_re_raised(db, tag):
    """WSV-U-04 — a failing commit is rolled back and re-raised.
    Rules: `update_status` R3; TC4"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_status(db, signup_id=a.id, status_value="DECLINED")

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, a.id).status == "PENDING"


# [claude] WSV-U-05
def test_wsv_u_05__a_status_over_20_characters_fails_at_the_flush_and_leaves_the_session_needing_a_rollback(
    db, tag,
):
    """WSV-U-05 — a status over 20 characters fails at the flush and leaves the session needing a rollback.
    Rules: `update_status` R3, Errors"""
    a = mk_signup(db, f"ann.{tag}@x.com")
    a_id = a.id
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        svc.update_status(db, signup_id=a_id, status_value="X" * 21)
    # Then 2
    with pytest.raises(PendingRollbackError):
        db.execute(text("SELECT 1"))
    # Then 3
    db.rollback()
    assert reread(db, a_id).status == "PENDING"


# --------------------------------------------------------------------------- #
# WaitlistService.list_signups
# --------------------------------------------------------------------------- #

# [claude] WSV-L-01
def test_wsv_l_01__items_and_total_come_from_the_dao_skip_and_limit_are_echoed(db, tag):
    """WSV-L-01 — items and total come from the DAO; skip and limit are echoed.
    Rules: `list_signups` R1, Returns"""
    a = mk_signup(db, f"a.{tag}@x.com", created_at=T2)
    mk_signup(db, f"b.{tag}@x.com", created_at=T3)
    mk_signup(db, f"c.{tag}@x.com", created_at=T1)
    commit_point(db)
    result = svc.list_signups(db, skip=1, limit=1, search=tag, wants_product_updates=None)

    # Then 1
    assert result.total == 3
    # Then 2
    assert result.skip == 1
    assert result.limit == 1
    # Then 3
    assert ids(result.items) == [a.id]
    # Then 4
    assert isinstance(result.items[0], WaitlistSignupItem)


# [claude] WSV-L-02
def test_wsv_l_02__status_value_reaches_the_dao_as_the_status_filter(db, tag):
    """WSV-L-02 — status_value reaches the DAO as the status filter.
    Rules: `list_signups` R1"""
    a = mk_signup(db, f"a.{tag}@x.com", status="CONTACTED")
    mk_signup(db, f"b.{tag}@x.com")
    commit_point(db)
    result = svc.list_signups(
        db, skip=0, limit=1000, search=tag, wants_product_updates=None, status_value="CONTACTED",
    )

    # Then 1
    assert ids(result.items) == [a.id]
    # Then 2
    assert result.total == 1


# [claude] WSV-L-03
def test_wsv_l_03__wants_product_updates_reaches_the_dao(db, tag):
    """WSV-L-03 — wants_product_updates reaches the DAO.
    Rules: `list_signups` R1"""
    mk_signup(db, f"a.{tag}@x.com", wants_product_updates=True)
    b = mk_signup(db, f"b.{tag}@x.com")
    commit_point(db)
    result = svc.list_signups(db, skip=0, limit=1000, search=tag, wants_product_updates=False)

    # Then 1
    assert ids(result.items) == [b.id]
    # Then 2
    assert result.total == 1


# [claude] WSV-L-04
def test_wsv_l_04__a_stored_status_outside_the_four_makes_the_list_fail(db, tag):
    """WSV-L-04 — a stored status outside the four makes the list fail.
    Rules: `list_signups` R2, Errors"""
    a = mk_signup(db, f"a.{tag}@x.com", status="legacy")
    commit_point(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        svc.list_signups(db, skip=0, limit=1000, search=tag, wants_product_updates=None)
    # Then 2
    assert reread(db, a.id).status == "legacy"


# [claude] WSV-L-05
def test_wsv_l_05__the_list_neither_commits_nor_rolls_back(db, tag):
    """WSV-L-05 — the list neither commits nor rolls back.
    Rules: `list_signups` R3; TC6"""
    a = mk_signup(db, f"a.{tag}@x.com")
    b = mk_signup(db, f"b.{tag}@x.com")
    commit_point(db)
    mk_signup(db, f"p.{tag}@x.com")
    b.first_name = "Edited"
    result = svc.list_signups(db, skip=0, limit=1000, search=f"a.{tag}", wants_product_updates=None)

    # Then 1
    assert ids(result.items) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count(db, f"p.{tag}@x.com") == 0
    # Then 5
    assert reread(db, b.id).first_name == "Zed"


# [claude] WSV-L-06
def test_wsv_l_06__pass_through_bug_1410_underscore_in_the_search_matches_only_a_literal_underscore(db, tag):
    """WSV-L-06 — pass-through BUG-1410: _ in the search matches only a literal _.
    Rules: `list_signups` R1 [BUG-1410]"""
    a = mk_signup(db, f"a_b.{tag}@x.com")
    mk_signup(db, f"axb.{tag}@x.com")
    commit_point(db)
    result = svc.list_signups(db, skip=0, limit=1000, search=f"a_b.{tag}", wants_product_updates=None)

    # Then 1
    assert isinstance(result.items, list)
    # Then 2
    assert ids(result.items) == [a.id]
    # Then 3
    assert result.total == 1


# [claude] WSV-L-07
def test_wsv_l_07__pass_through_bug_1411_on_a_created_at_tie_the_higher_id_comes_first(db, tag):
    """WSV-L-07 — pass-through BUG-1411: on a created_at tie the higher id comes first.
    Rules: `list_signups` R1 [BUG-1411]"""
    a = mk_signup(db, f"a.{tag}@x.com", created_at=T2)
    b = mk_signup(db, f"b.{tag}@x.com", created_at=T2)
    c = mk_signup(db, f"c.{tag}@x.com", created_at=T2)
    a.first_name = "Amy"
    db.flush()
    commit_point(db)
    result = svc.list_signups(db, skip=0, limit=1000, search=tag, wants_product_updates=None)

    # Then 1
    assert len(result.items) == 3
    # Then 2
    assert ids(result.items) == [c.id, b.id, a.id]
