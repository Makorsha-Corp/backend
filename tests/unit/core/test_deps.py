"""Unit tests for app/core/deps.py.

Implements tests/unit/core/deps.cases.md (revision 2), one test per case.
Real Postgres session (`db` fixture). Nothing external is mocked (spec: none).
`get_db` is driven with a spy session factory patched over
`app.core.deps.SessionLocal` (a Conventions item, not an external mock).
HTTPBearer behavior and header-name case-insensitivity are exercised through a
minimal FastAPI() app + TestClient with `get_db` overridden; the real app is
never started.
"""
import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.core.deps as deps_module
from app.core.config import settings
from app.core.deps import (
    get_current_active_user,
    get_current_user,
    get_current_workspace,
    get_db,
    get_platform_admin,
)
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

BUG_440 = "BUG-440: Non-members can enumerate which workspace ids exist"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #


def _now() -> int:
    return int(time.time())


# Convention "FUT" = real now + 15 min, "PAST" = real now - 60 s (epoch seconds)
def FUT() -> int:
    return _now() + 15 * 60


def PAST() -> int:
    return _now() - 60


# Convention "tok(claims, key, alg)"
def tok(claims, key=None, alg=None) -> str:
    return jwt.encode(
        claims,
        settings.SECRET_KEY if key is None else key,
        algorithm=settings.ALGORITHM if alg is None else alg,
    )


# Convention "Creds(t)"
def Creds(t: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=t)


# Convention "req(h)" / "req_none"
def req(h: str) -> Request:
    return Request({"type": "http", "headers": [(b"x-workspace-id", h.encode())]})


def req_none() -> Request:
    return Request({"type": "http", "headers": []})


# Convention "E401"
def assert_e401(exc: HTTPException) -> None:
    assert exc.status_code == 401
    assert exc.detail == "Could not validate credentials"
    assert exc.headers == {"WWW-Authenticate": "Bearer"}


# Convention "DENIED" (pass counterparts of BUG-440 cases only)
def assert_denied(call) -> None:
    with pytest.raises(HTTPException) as exc:
        call()
    assert exc.value.status_code in (403, 404)


# Local builder: workspace_members row (role explicit, per Conventions "Rows").
# Worth promoting to tests/unit/factories.py as make_workspace_member.
def add_member(db: Session, ws, user, role="member", status="active") -> WorkspaceMember:
    row = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=role, status=status)
    db.add(row)
    db.flush()
    return row


def reread_profile(db: Session, pid: int) -> Profile:
    db.expire_all()
    return db.execute(select(Profile).where(Profile.id == pid)).scalar_one()


def reread_workspace(db: Session, wid: int) -> Workspace:
    db.expire_all()
    return db.execute(select(Workspace).where(Workspace.id == wid)).scalar_one()


def memberships(db: Session, uid: int) -> list[tuple]:
    db.expire_all()
    rows = db.execute(
        select(WorkspaceMember).where(WorkspaceMember.user_id == uid).order_by(WorkspaceMember.id)
    ).scalars().all()
    return [(m.id, m.workspace_id, m.role, m.status) for m in rows]


# Convention "W1, W2"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1": email u1@example.com, non-admin, active member of W1
@pytest.fixture
def u1(db, w1):
    u = make_profile(db, email="u1@example.com", is_platform_admin=False)
    add_member(db, w1, u, role="member", status="active")
    return u


# Convention "U3": non-admin, no memberships
@pytest.fixture
def u3(db):
    return make_profile(db, is_platform_admin=False)


# Convention "A": platform admin, no memberships
@pytest.fixture
def A(db):
    return make_profile(db, is_platform_admin=True)


# Convention "MISSING" / "NOUSER"
@pytest.fixture
def MISSING(w1):
    return w1.id + 1_000_000


@pytest.fixture
def NOUSER(u1):
    return u1.id + 1_000_000


def default_claims(u1) -> dict:
    return {"sub": str(u1.id), "email": "u1@example.com", "exp": FUT()}


# Convention "Spy session (get_db cases)"
class SpySession:
    def __init__(self):
        self.close_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def close(self):
        self.close_count += 1

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


class SpyFactory:
    def __init__(self):
        self.calls = 0
        self.made: list[SpySession] = []

    def __call__(self):
        self.calls += 1
        s = SpySession()
        self.made.append(s)
        return s


@pytest.fixture
def spy(monkeypatch):
    f = SpyFactory()
    monkeypatch.setattr(deps_module, "SessionLocal", f)
    return f


# Convention "App client (TestClient cases only)"
@pytest.fixture
def client_ctx(db):
    app = FastAPI()
    counter = {"n": 0}

    @app.get("/me")
    def me(user: Profile = Depends(get_current_user)):
        return {"id": user.id}

    @app.get("/ws")
    def ws(workspace: Workspace = Depends(get_current_workspace)):
        return {"id": workspace.id}

    def _db_override():
        counter["n"] += 1
        yield db

    app.dependency_overrides[get_db] = _db_override
    with TestClient(app) as client:
        yield SimpleNamespace(app=app, client=client, counter=counter)


# --------------------------------------------------------------------------- #
# get_db
# --------------------------------------------------------------------------- #


def test_deps_db_01__yields_new_session(spy):
    """DEPS-DB-01 — advancing get_db yields the factory's session; one factory call.
    Rules: get_db R1."""
    g = get_db()
    s = next(g)
    g.close()
    assert s is spy.made[0]
    assert spy.calls == 1


def test_deps_db_02__separate_sessions_per_call(spy):
    """DEPS-DB-02 — two get_db() calls give two sessions; closing one leaves the other open.
    Rules: get_db R1."""
    g1 = get_db()
    g2 = get_db()
    s1 = next(g1)
    s2 = next(g2)
    g1.close()
    assert s1 is not s2
    assert spy.calls == 2
    assert s1.close_count == 1
    assert s2.close_count == 0
    g2.close()
    assert s2.close_count == 1


def test_deps_db_03__close_on_normal_exit(spy):
    """DEPS-DB-03 — closing the generator closes the session once, no commit/rollback.
    Rules: get_db R2, R4."""
    g = get_db()
    s = next(g)
    g.close()
    assert s.close_count == 1
    assert s.commit_count == 0
    assert s.rollback_count == 0


def test_deps_db_04__close_on_exhaustion(spy):
    """DEPS-DB-04 — exhausting the generator closes the session once, no commit/rollback.
    Rules: get_db R2, R4."""
    g = get_db()
    s = next(g)
    with pytest.raises(StopIteration):
        next(g)
    assert s.close_count == 1
    assert s.commit_count == 0
    assert s.rollback_count == 0


def test_deps_db_05__exception_propagates_and_closes(spy):
    """DEPS-DB-05 — a thrown ValueError propagates unchanged; session closed once.
    Rules: get_db R3, R4."""
    exc = ValueError("boom")
    g = get_db()
    s = next(g)
    with pytest.raises(ValueError) as raised:
        g.throw(exc)
    assert raised.value is exc
    assert str(raised.value) == "boom"
    assert s.close_count == 1
    assert s.commit_count == 0
    assert s.rollback_count == 0


def test_deps_db_06__http_exception_propagates_and_closes(spy):
    """DEPS-DB-06 — a thrown HTTPException propagates as the same object; session closed.
    Rules: get_db R3."""
    exc = HTTPException(status_code=404, detail="x")
    g = get_db()
    s = next(g)
    with pytest.raises(HTTPException) as raised:
        g.throw(exc)
    assert raised.value is exc
    assert raised.value.status_code == 404
    assert raised.value.detail == "x"
    assert s.close_count == 1


def test_deps_db_07__real_session_autoflush_off():
    """DEPS-DB-07 — real SessionLocal yields a Session with autoflush off (no query run).
    Rules: get_db Returns."""
    g = get_db()
    s = next(g)
    try:
        assert isinstance(s, Session)
        assert s.autoflush is False
    finally:
        g.close()


# --------------------------------------------------------------------------- #
# get_current_user — via app client (HTTPBearer)
# --------------------------------------------------------------------------- #


def test_deps_cu_01__no_authorization_header(client_ctx, u1):
    """DEPS-CU-01 — no Authorization header -> 401 Not authenticated, no db access.
    Rules: get_current_user R1."""
    r = client_ctx.client.get("/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert client_ctx.counter["n"] == 0


def test_deps_cu_02__basic_scheme_rejected(client_ctx, u1):
    """DEPS-CU-02 — Basic scheme -> 401 Not authenticated, no db access.
    Rules: get_current_user R1."""
    r = client_ctx.client.get("/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert client_ctx.counter["n"] == 0


def test_deps_cu_03__empty_bearer_token(client_ctx, u1):
    """DEPS-CU-03 — 'Bearer ' with empty token -> 401 Not authenticated, no db access.
    Rules: get_current_user R1."""
    r = client_ctx.client.get("/me", headers={"Authorization": "Bearer "})
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert client_ctx.counter["n"] == 0


def test_deps_cu_04__valid_bearer_token(client_ctx, u1):
    """DEPS-CU-04 — valid Bearer token -> 200 with the user's id.
    Rules: get_current_user R1."""
    r = client_ctx.client.get("/me", headers={"Authorization": f"Bearer {tok(default_claims(u1))}"})
    assert r.status_code == 200
    assert r.json() == {"id": u1.id}


def test_deps_cu_05__lowercase_bearer_scheme(client_ctx, u1):
    """DEPS-CU-05 — lowercase 'bearer' scheme accepted.
    Rules: get_current_user R2."""
    r = client_ctx.client.get("/me", headers={"Authorization": f"bearer {tok(default_claims(u1))}"})
    assert r.status_code == 200
    assert r.json() == {"id": u1.id}


def test_deps_cu_06__lowercase_bearer_reaches_decoding(client_ctx, u1):
    """DEPS-CU-06 — 'bearer abc' reaches decoding -> 401 Could not validate credentials.
    Rules: get_current_user R2, R4."""
    r = client_ctx.client.get("/me", headers={"Authorization": "bearer abc"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Could not validate credentials"
    assert r.headers["WWW-Authenticate"] == "Bearer"


# --------------------------------------------------------------------------- #
# get_current_user — direct calls
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "make_token",
    [
        pytest.param(lambda u: "not-a-jwt", id="DEPS-CU-07-random"),
        pytest.param(lambda u: tok(default_claims(u))[:-10], id="DEPS-CU-07-truncated"),
        pytest.param(lambda u: "!!!.@@@.###", id="DEPS-CU-07-badb64"),
    ],
)
def test_deps_cu_07__malformed_token(db, u1, make_token):
    """DEPS-CU-07 — malformed tokens raise E401; U1 unchanged.
    Rules: get_current_user R3, R4."""
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(make_token(u1)), db)
    assert_e401(exc.value)
    assert reread_profile(db, u1.id).email == "u1@example.com"


def test_deps_cu_08__wrong_secret(db, u1):
    """DEPS-CU-08 — token signed with another secret -> E401.
    Rules: get_current_user R3, R5."""
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(default_claims(u1), key="wrong-secret")), db)
    assert_e401(exc.value)


def test_deps_cu_09__wrong_algorithm(db, u1):
    """DEPS-CU-09 — HS512 with the right secret -> E401.
    Rules: get_current_user R6."""
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(default_claims(u1), alg="HS512")), db)
    assert_e401(exc.value)


def test_deps_cu_10__alg_none_unsigned(db, u1):
    """DEPS-CU-10 — unsigned alg=none token -> E401.
    Rules: get_current_user R6."""
    t = jwt.encode(default_claims(u1), None, algorithm="none")
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(t), db)
    assert_e401(exc.value)


def test_deps_cu_11__expired(db, u1):
    """DEPS-CU-11 — exp in the past -> E401.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "exp": PAST()}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_12__exp_soon_still_valid(db, u1):
    """DEPS-CU-12 — exp = now + 60 s -> profile returned.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "exp": _now() + 60}
    user = get_current_user(Creds(tok(claims)), db)
    assert user.id == u1.id
    assert user.email == "u1@example.com"


def test_deps_cu_13__nbf_in_future(db, u1):
    """DEPS-CU-13 — nbf one hour ahead -> E401.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "nbf": _now() + 3600}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_14__nbf_in_past(db, u1):
    """DEPS-CU-14 — nbf in the past -> profile returned.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "nbf": PAST()}
    user = get_current_user(Creds(tok(claims)), db)
    assert user.id == u1.id


def test_deps_cu_15__exp_non_numeric(db, u1):
    """DEPS-CU-15 — exp = "tomorrow" -> E401.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "exp": "tomorrow"}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_16__iat_non_numeric(db, u1):
    """DEPS-CU-16 — iat = "yesterday" -> E401.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "iat": "yesterday"}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_17__nbf_non_numeric(db, u1):
    """DEPS-CU-17 — nbf = "soon" -> E401.
    Rules: get_current_user R7."""
    claims = {**default_claims(u1), "nbf": "soon"}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_18__no_exp_accepted(db, u1):
    """DEPS-CU-18 — token without exp is accepted.
    Rules: get_current_user R8."""
    user = get_current_user(Creds(tok({"sub": str(u1.id), "email": "u1@example.com"})), db)
    assert user.id == u1.id


def test_deps_cu_19__no_sub(db, u1):
    """DEPS-CU-19 — token without sub -> E401.
    Rules: get_current_user R9."""
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok({"email": "u1@example.com", "exp": FUT()})), db)
    assert_e401(exc.value)


def test_deps_cu_20__numeric_sub(db, u1):
    """DEPS-CU-20 — sub as a JSON number -> E401.
    Rules: get_current_user R10."""
    claims = {**default_claims(u1), "sub": u1.id}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


@pytest.mark.parametrize(
    "sub",
    [
        pytest.param("abc", id="DEPS-CU-21-abc"),
        pytest.param("", id="DEPS-CU-21-empty"),
        pytest.param("5.0", id="DEPS-CU-21-float"),
    ],
)
def test_deps_cu_21__unparseable_sub(db, u1, sub):
    """DEPS-CU-21 — sub int() cannot parse -> E401.
    Rules: get_current_user R11."""
    claims = {**default_claims(u1), "sub": sub}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_22__valid_token_returns_profile(db, u1):
    """DEPS-CU-22 — valid token returns U1 unchanged.
    Rules: get_current_user R12, R14."""
    user = get_current_user(Creds(tok(default_claims(u1))), db)
    assert user.id == u1.id
    assert user.email == "u1@example.com"
    assert user.is_platform_admin is False
    again = reread_profile(db, u1.id)
    assert again.email == "u1@example.com"
    assert again.is_platform_admin is False


@pytest.mark.parametrize(
    "fmt",
    [
        pytest.param(" {} ", id="DEPS-CU-23-spaces"),
        pytest.param("+{}", id="DEPS-CU-23-plus"),
        pytest.param("0_{}", id="DEPS-CU-23-underscore"),
    ],
)
def test_deps_cu_23__int_accepted_sub_forms(db, u1, fmt):
    """DEPS-CU-23 — sub forms int() accepts resolve U1.
    Rules: get_current_user R12."""
    claims = {**default_claims(u1), "sub": fmt.format(u1.id)}
    user = get_current_user(Creds(tok(claims)), db)
    assert user.id == u1.id


@pytest.mark.parametrize(
    "sub",
    [pytest.param("-1", id="DEPS-CU-24-neg"), pytest.param("0", id="DEPS-CU-24-zero")],
)
def test_deps_cu_24__nonpositive_sub(db, u1, sub):
    """DEPS-CU-24 — "-1" / "0" parse and match no user -> E401.
    Rules: get_current_user R12, R13."""
    claims = {**default_claims(u1), "sub": sub}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_25__unknown_user(db, u1, NOUSER):
    """DEPS-CU-25 — sub with no profile -> E401.
    Rules: get_current_user R13."""
    claims = {**default_claims(u1), "sub": str(NOUSER)}
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(tok(claims)), db)
    assert_e401(exc.value)


def test_deps_cu_26__deleted_user(db, u1):
    """DEPS-CU-26 — token for a profile deleted afterwards -> E401.
    Rules: get_current_user R13."""
    u2 = make_profile(db)
    t = tok({"sub": str(u2.id), "exp": FUT()})
    db.delete(u2)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        get_current_user(Creds(t), db)
    assert_e401(exc.value)


def test_deps_cu_27__other_claims_ignored(db, u1, MISSING):
    """DEPS-CU-27 — email/workspace_id claims are ignored; U1 unchanged.
    Rules: get_current_user R14."""
    claims = {"sub": str(u1.id), "email": "other@example.com", "workspace_id": MISSING, "exp": FUT()}
    user = get_current_user(Creds(tok(claims)), db)
    assert user.id == u1.id
    assert user.email == "u1@example.com"
    assert reread_profile(db, u1.id).email == "u1@example.com"


def test_deps_cu_28__platform_admin_resolves(db, A):
    """DEPS-CU-28 — platform admin resolves like anyone else.
    Rules: get_current_user R15."""
    user = get_current_user(Creds(tok({"sub": str(A.id), "exp": FUT()})), db)
    assert user.id == A.id
    assert user.is_platform_admin is True


# --------------------------------------------------------------------------- #
# get_current_active_user
# --------------------------------------------------------------------------- #


def test_deps_au_01__returns_same_profile(db, u1):
    """DEPS-AU-01 — returns U1 itself; U1 unchanged.
    Rules: get_current_active_user R1."""
    result = get_current_active_user(u1)
    assert result is u1
    again = reread_profile(db, u1.id)
    assert again.email == "u1@example.com"
    assert again.is_platform_admin is False


def test_deps_au_02__returns_admin(db, A):
    """DEPS-AU-02 — returns A itself, still admin.
    Rules: get_current_active_user R1."""
    result = get_current_active_user(A)
    assert result is A
    assert result.is_platform_admin is True


def test_deps_au_03__transient_profile(db):
    """DEPS-AU-03 — transient profile returned as is; nothing persisted.
    Rules: get_current_active_user R1."""
    p = Profile(email="p@example.com")
    result = get_current_active_user(p)
    assert result is p
    db.expire_all()
    assert db.execute(select(Profile).where(Profile.email == "p@example.com")).first() is None


# --------------------------------------------------------------------------- #
# get_current_workspace
# --------------------------------------------------------------------------- #


def test_deps_cw_01__active_member_gets_workspace(db, w1, u1):
    """DEPS-CW-01 — active member receives W1; nothing changes.
    Rules: get_current_workspace R7."""
    before_ws = reread_workspace(db, w1.id)
    before = (before_ws.name, before_ws.subscription_status)
    before_m = memberships(db, u1.id)
    ws = get_current_workspace(req(str(w1.id)), db, u1)
    assert ws.id == w1.id
    after_ws = reread_workspace(db, w1.id)
    assert (after_ws.name, after_ws.subscription_status) == before
    after_m = memberships(db, u1.id)
    assert [m[3] for m in after_m if m[1] == w1.id] == ["active"]
    assert after_m == before_m


def test_deps_cw_02__header_missing(db, w1, u1):
    """DEPS-CW-02 — no header -> 400 header required; nothing changes.
    Rules: get_current_workspace R1."""
    before_ws = reread_workspace(db, w1.id)
    before = (before_ws.name, before_ws.subscription_status)
    before_m = memberships(db, u1.id)
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req_none(), db, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "X-Workspace-ID header is required"
    after_ws = reread_workspace(db, w1.id)
    assert (after_ws.name, after_ws.subscription_status) == before
    assert memberships(db, u1.id) == before_m


def test_deps_cw_03__header_empty(db, w1, u1):
    """DEPS-CW-03 — empty header -> 400 header required.
    Rules: get_current_workspace R2."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(""), db, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "X-Workspace-ID header is required"


@pytest.mark.parametrize(
    "h",
    [
        pytest.param("abc", id="DEPS-CW-04-abc"),
        pytest.param("5.0", id="DEPS-CW-04-float"),
        pytest.param("0x5", id="DEPS-CW-04-hex"),
        pytest.param("   ", id="DEPS-CW-04-blank"),
    ],
)
def test_deps_cw_04__header_not_integer(db, w1, u1, h):
    """DEPS-CW-04 — non-integer header -> 400 must be a valid integer.
    Rules: get_current_workspace R3."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(h), db, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "X-Workspace-ID must be a valid integer"


@pytest.mark.parametrize(
    "fmt",
    [
        pytest.param(" {} ", id="DEPS-CW-05-spaces"),
        pytest.param("+{}", id="DEPS-CW-05-plus"),
        pytest.param("0_{}", id="DEPS-CW-05-underscore"),
    ],
)
def test_deps_cw_05__int_accepted_header_forms(db, w1, u1, fmt):
    """DEPS-CW-05 — header forms int() accepts resolve W1.
    Rules: get_current_workspace R4."""
    ws = get_current_workspace(req(fmt.format(w1.id)), db, u1)
    assert ws.id == w1.id


@pytest.mark.parametrize(
    "h,detail",
    [
        pytest.param("-1", "Workspace with ID -1 not found", id="DEPS-CW-06-neg"),
        pytest.param("0", "Workspace with ID 0 not found", id="DEPS-CW-06-zero"),
        pytest.param(
            "99999999999999999999",
            "Workspace with ID 99999999999999999999 not found",
            id="DEPS-CW-06-huge",
        ),
    ],
)
def test_deps_cw_06__parsed_but_no_workspace(db, w1, u1, h, detail):
    """DEPS-CW-06 — negative/zero/huge ids -> 404 not found, no other exception type.
    Rules: get_current_workspace R4, R5."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(h), db, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == detail


def test_deps_cw_07__missing_detail_uses_parsed_int(db, w1, u1, MISSING):
    """DEPS-CW-07 — ' 0<MISSING> ' -> 404 with the parsed integer in the detail.
    Rules: get_current_workspace R5."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(f" 0{MISSING} "), db, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Workspace with ID {MISSING} not found"


def test_deps_cw_08__admin_does_not_bypass_existence(db, A, MISSING):
    """DEPS-CW-08 — platform admin with a missing id -> 404.
    Rules: get_current_workspace R5."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(str(MISSING)), db, A)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Workspace with ID {MISSING} not found"


def test_deps_cw_09__admin_any_workspace(db, w2, A):
    """DEPS-CW-09 — admin gets W2 without a membership; none created.
    Rules: get_current_workspace R6."""
    ws = get_current_workspace(req(str(w2.id)), db, A)
    assert ws.id == w2.id
    assert memberships(db, A.id) == []


def test_deps_cw_10__header_check_before_admin(db, A):
    """DEPS-CW-10 — admin with 'abc' header -> 400 (header checks first).
    Rules: get_current_workspace R1-R5 precedence."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req("abc"), db, A)
    assert exc.value.status_code == 400
    assert exc.value.detail == "X-Workspace-ID must be a valid integer"


@pytest.mark.xfail(strict=True, reason=BUG_440)
def test_deps_cw_11__non_member_indistinguishable_from_missing(db, w1, w2, u1, MISSING):
    """DEPS-CW-11 — non-member of W2 gets the same 404 as a missing id.
    Rules: get_current_workspace R8 [BUG-440]."""
    with pytest.raises(HTTPException) as first:
        get_current_workspace(req(str(w2.id)), db, u1)
    assert first.value.status_code == 404
    assert first.value.detail == f"Workspace with ID {w2.id} not found"
    with pytest.raises(HTTPException) as second:
        get_current_workspace(req(str(MISSING)), db, u1)
    assert first.value.status_code == second.value.status_code == 404
    assert second.value.detail == f"Workspace with ID {MISSING} not found"


def test_deps_cw_12__non_member_denied(db, w1, w2, u1):
    """DEPS-CW-12 — non-member of W2 is denied; no membership created.
    Rules: get_current_workspace R8."""
    assert_denied(lambda: get_current_workspace(req(str(w2.id)), db, u1))
    assert [m for m in memberships(db, u1.id) if m[1] == w2.id] == []


@pytest.mark.xfail(strict=True, reason=BUG_440)
def test_deps_cw_13__no_memberships_gets_404(db, w1, u3):
    """DEPS-CW-13 — user with no memberships -> 404 not found.
    Rules: get_current_workspace R8 [BUG-440]."""
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(str(w1.id)), db, u3)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Workspace with ID {w1.id} not found"


NON_ACTIVE = ["suspended", "invited", "Active"]


@pytest.mark.xfail(strict=True, reason=BUG_440)
@pytest.mark.parametrize(
    "status", [pytest.param(s, id=f"DEPS-CW-14-{s}") for s in NON_ACTIVE]
)
def test_deps_cw_14__non_active_membership_gets_404(db, w1, status):
    """DEPS-CW-14 — membership not exactly 'active' -> 404 not found.
    Rules: get_current_workspace R9 [BUG-440]."""
    u2 = make_profile(db, is_platform_admin=False)
    add_member(db, w1, u2, role="member", status=status)
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(str(w1.id)), db, u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Workspace with ID {w1.id} not found"


@pytest.mark.parametrize(
    "status", [pytest.param(s, id=f"DEPS-CW-15-{s}") for s in NON_ACTIVE]
)
def test_deps_cw_15__non_active_membership_denied(db, w1, status):
    """DEPS-CW-15 — membership not exactly 'active' is denied; status unchanged.
    Rules: get_current_workspace R9."""
    u2 = make_profile(db, is_platform_admin=False)
    m = add_member(db, w1, u2, role="member", status=status)
    assert_denied(lambda: get_current_workspace(req(str(w1.id)), db, u2))
    db.expire_all()
    assert db.execute(
        select(WorkspaceMember.status).where(WorkspaceMember.id == m.id)
    ).scalar_one() == status


def _w3_fields(variant):
    now = utcnow()
    from datetime import timedelta

    if variant == "a":
        return {
            "subscription_status": "cancelled",
            "trial_ends_at": now - timedelta(days=60),
            "subscription_ends_at": now - timedelta(days=1),
        }
    return {"subscription_status": "trial", "trial_ends_at": now - timedelta(days=60)}


def _sub_fields(ws):
    return (ws.subscription_status, ws.trial_ends_at, ws.subscription_ends_at)


@pytest.mark.parametrize(
    "variant", [pytest.param("a", id="DEPS-CW-16-a"), pytest.param("b", id="DEPS-CW-16-b")]
)
def test_deps_cw_16__subscription_state_ignored_for_member(db, u1, variant):
    """DEPS-CW-16 — lapsed/cancelled workspace still returned to an active member.
    Rules: get_current_workspace R10, R7."""
    w3 = make_workspace(db, **_w3_fields(variant))
    add_member(db, w3, u1, role="member", status="active")
    before = _sub_fields(reread_workspace(db, w3.id))
    ws = get_current_workspace(req(str(w3.id)), db, u1)
    assert ws.id == w3.id
    assert _sub_fields(reread_workspace(db, w3.id)) == before


def test_deps_cw_17__subscription_state_ignored_for_admin(db, A):
    """DEPS-CW-17 — cancelled workspace returned to a platform admin.
    Rules: get_current_workspace R10, R6."""
    w3 = make_workspace(db, **_w3_fields("a"))
    ws = get_current_workspace(req(str(w3.id)), db, A)
    assert ws.id == w3.id


def test_deps_cw_18__plain_object_member(db, w1, u1):
    """DEPS-CW-18 — object without is_platform_admin, id of an active member -> W1.
    Rules: get_current_workspace R11, R7."""
    obj = SimpleNamespace(id=u1.id)
    ws = get_current_workspace(req(str(w1.id)), db, obj)
    assert ws.id == w1.id


@pytest.mark.xfail(strict=True, reason=BUG_440)
def test_deps_cw_19__plain_object_non_member_gets_404(db, w2, u1):
    """DEPS-CW-19 — plain object not in W2 -> 404 not found.
    Rules: get_current_workspace R11, R8 [BUG-440]."""
    obj = SimpleNamespace(id=u1.id)
    with pytest.raises(HTTPException) as exc:
        get_current_workspace(req(str(w2.id)), db, obj)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Workspace with ID {w2.id} not found"


def test_deps_cw_20__plain_object_not_admin(db, w2, u1):
    """DEPS-CW-20 — plain object is not treated as admin: denied.
    Rules: get_current_workspace R11."""
    obj = SimpleNamespace(id=u1.id)
    assert_denied(lambda: get_current_workspace(req(str(w2.id)), db, obj))


def test_deps_cw_21__header_name_case_insensitive(client_ctx, w1, u1):
    """DEPS-CW-21 — X-WORKSPACE-ID and x-workspace-id both work through FastAPI.
    Rules: get_current_workspace Inputs (header name case-insensitive)."""
    client_ctx.app.dependency_overrides[get_current_user] = lambda: u1
    r1 = client_ctx.client.get("/ws", headers={"X-WORKSPACE-ID": str(w1.id)})
    r2 = client_ctx.client.get("/ws", headers={"x-workspace-id": str(w1.id)})
    assert r1.status_code == 200
    assert r1.json() == {"id": w1.id}
    assert r2.status_code == 200
    assert r2.json() == {"id": w1.id}


def test_deps_cw_22__admin_without_membership(db, w1, A):
    """DEPS-CW-22 — admin without W1 membership gets W1.
    Rules: get_current_workspace R6."""
    ws = get_current_workspace(req(str(w1.id)), db, A)
    assert ws.id == w1.id


def test_deps_cw_23__no_memberships_denied(db, w1, u3):
    """DEPS-CW-23 — user with no memberships is denied; none created.
    Rules: get_current_workspace R8."""
    assert_denied(lambda: get_current_workspace(req(str(w1.id)), db, u3))
    assert memberships(db, u3.id) == []


# --------------------------------------------------------------------------- #
# get_platform_admin
# --------------------------------------------------------------------------- #


def test_deps_pa_01__admin_passes(db, A):
    """DEPS-PA-01 — admin without memberships passes; still admin.
    Rules: get_platform_admin R1, R4."""
    result = get_platform_admin(A)
    assert result is A
    assert reread_profile(db, A.id).is_platform_admin is True


def test_deps_pa_02__non_admin_rejected(db, u1):
    """DEPS-PA-02 — non-admin -> 403; U1 unchanged.
    Rules: get_platform_admin R2."""
    with pytest.raises(HTTPException) as exc:
        get_platform_admin(u1)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Platform admin access required"
    assert reread_profile(db, u1.id).is_platform_admin is False


def test_deps_pa_03__workspace_owner_rejected(db, w1):
    """DEPS-PA-03 — workspace owner who is not admin -> 403; membership unchanged.
    Rules: get_platform_admin R4."""
    o = make_profile(db, is_platform_admin=False)
    add_member(db, w1, o, role="owner", status="active")
    before = memberships(db, o.id)
    with pytest.raises(HTTPException) as exc:
        get_platform_admin(o)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Platform admin access required"
    assert memberships(db, o.id) == before


@pytest.mark.parametrize(
    "obj",
    [
        pytest.param(SimpleNamespace(id=1), id="DEPS-PA-04"),
        pytest.param(SimpleNamespace(id=1, is_platform_admin=None), id="DEPS-PA-05"),
    ],
)
def test_deps_pa_04_05__missing_or_none_flag_rejected(obj):
    """DEPS-PA-04 / DEPS-PA-05 — no is_platform_admin attribute, or None -> 403.
    Rules: get_platform_admin R3."""
    with pytest.raises(HTTPException) as exc:
        get_platform_admin(obj)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Platform admin access required"
