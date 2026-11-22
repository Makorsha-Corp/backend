"""Unit tests for app/services/auth_service.py.

Implements tests/unit/services/auth_service.cases.md (revision 5), one test
per card, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the service's commits are safe and the fixture's
outer rollback discards everything.

Patched: the four `utcnow` clocks (Conventions "clock"), the Cloudinary delete
`destroy_resource` and the stamp settings (Conventions "dr", every ME card),
the commit / rollback / refresh spies and failures the cards name, the
failing access-token clock of AUTH-LI-13 / SW-14 ("failing issue"), the
race simulation RACE-EMAIL (AUTH-RG-11 ... 13) and the fake `refresh_token_dao`
of AUTH-TP-13. No email or network call exists in this module.

Normal mode: every test is written from its card and carries a
`# [claude] <ID>` comment. Standing rows and per-test values live on fixture
`S` (`S.UA`, `S.W1`, `S.EA` ...); `# Then N` marks the checks of Then line N.
"""

# ruff: noqa: DTZ001, SIM117, RUF059  (Conventions prescribe naive datetimes and nested `with` blocks; the cards unpack every result)
import re
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import (
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from app.dao.profile import DAOProfile
from app.models.profile import Profile
from app.models.refresh_token import RefreshToken
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_member import WorkspaceMember
from app.schemas.profile import ProfileMeUpdate
from app.schemas.response import ActionMessage  # noqa: F401  (Conventions import list)
from app.services.auth_service import (  # noqa: F401  (Conventions import list)
    AuthService,
    TokenPair,
    auth_service,
)
from tests.unit.factories import make_profile, make_subscription_plan, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = auth_service

MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)
US = timedelta(microseconds=1)
DAY = timedelta(days=1)
PAST = NOW - DAY
EARLY = datetime(2026, 3, 1, 8, 0, 0)
LATER = NOW + timedelta(days=10)
FAR = datetime(2099, 1, 1, 0, 0, 0)
NOW14 = NOW + timedelta(days=14)
EXP15 = int(datetime(2026, 3, 5, 12, 15, 0, tzinfo=timezone.utc).timestamp())

PW = "Correct-Horse-9"
PW2 = "Battery-Staple-7"
AGENT = "Mozilla/5.0 Test"
IP = "203.0.113.7"
HEX32 = r"[0-9a-f]{32}"

NOTMEM = "You are not a member of this workspace"
TAKEN = "An account with this email already exists. Try logging in instead."
BADLOGIN = "Invalid email or password"
EXPIRED_INV = "Invitation has expired. Please request a new invitation."

TOKEN = "0123456789abcdef0123456789abcdef"
TOKEN2 = "fedcba9876543210fedcba9876543210"
ATT = "ws-12/9f2c" + TOKEN
SRV = "https://res.cloudinary.com/demo-cloud/image/authenticated/"
FOREIGN = "saved_stamp.public_id is not a stamp of this user"
KIND_MSG = "saved_stamp.kind must be 'vector' or 'image'."


def OWN(U):
    """Convention OWN(U): the minted stamp public_id of profile U."""
    return f"development/profiles/{U.id}/stamp-{TOKEN}"


def OWN2(U):
    """Convention OWN2(U): OWN(U) with TOKEN2."""
    return f"development/profiles/{U.id}/stamp-{TOKEN2}"


def IMG(pid):
    """Convention IMG(pid): a fresh image stamp dict."""
    return {
        "kind": "image",
        "public_id": pid,
        "url": "https://tracker.example/p.png",
        "width": 10,
        "height": 10,
    }


def VEC_():
    """Convention VEC: a fresh vector stamp dict (use the module constant VEC
    for comparisons; it is never mutated)."""
    return {
        "kind": "vector",
        "strokes": [{"color": "#000000", "width": 0.5, "points": []}],
        "viewBox": {"width": 100, "height": 50},
    }


VEC = VEC_()


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows and per-test values (fixture S)
# --------------------------------------------------------------------------- #


@pytest.fixture
def S(db):
    """Standing rows 1-4 of Conventions plus the per-test TAG values.

    S.TAG, S.E0 ... S.EN, S.LOWER / S.MIXED / S.UPPER, S.RAW(k), S.FAM1,
    S.FAM2, S.WSNAME, S.SL; S.PL0-2, S.U0 ... S.UQ, S.W0-2, S.M0 / S.MO / S.M2.
    """
    s = SimpleNamespace()
    s.TAG = uuid.uuid4().hex[:8]
    t = s.TAG
    s.E0 = f"zed.{t}@acme.com"
    s.EO = f"own.{t}@acme.com"
    s.EA = f"ann.{t}@acme.com"
    s.EB = f"bob.{t}@acme.com"
    s.EC = f"cat.{t}@acme.com"
    s.E2 = f"two.{t}@acme.com"
    s.EQ = f"qin.{t}@acme.com"
    s.EN = f"new.{t}@acme.com"
    s.LOWER = f"ann.lee.{t}@example.com"
    s.MIXED = f"Ann.Lee.{t}@example.com"
    s.UPPER = f"ANN.LEE.{t.upper()}@EXAMPLE.COM"
    s.RAW1, s.RAW2, s.RAW3, s.RAW4, s.RAW5, s.RAW6 = (f"raw-{k}-{t}" for k in range(1, 7))
    s.FAM1 = uuid.uuid4().hex
    s.FAM2 = uuid.uuid4().hex
    s.WSNAME = f"Acme Steel {t}"
    s.SL = f"acme-steel-{t}"

    s.PL0 = make_subscription_plan(db, max_members=10)
    s.PL1 = make_subscription_plan(db, max_members=10)
    s.PL2 = make_subscription_plan(db, max_members=10)
    s.U0 = make_profile(db, email=s.E0, name="Zara Zero")
    s.UO = make_profile(db, email=s.EO, name="Olive Owner")
    s.UA = make_profile(db, email=s.EA, name="Ann Lee")
    s.UB = make_profile(db, email=s.EB, name="Bob Roy")
    s.UC = make_profile(db, email=s.EC, name="Cat Kim")
    s.U2 = make_profile(db, email=s.E2, name="Tom Two")
    s.UQ = make_profile(db, email=s.EQ, name="Quinn Extra")
    s.W0 = make_workspace(db, subscription_plan_id=s.PL0.id, owner_user_id=s.U0.id)
    s.W1 = make_workspace(db, name="Acme Works", subscription_plan_id=s.PL1.id, owner_user_id=s.UO.id)
    s.W2 = make_workspace(db, name="Tom Works", subscription_plan_id=s.PL2.id, owner_user_id=s.U2.id)
    s.M0 = _add(db, WorkspaceMember(workspace_id=s.W0.id, user_id=s.U0.id, role="owner", status="active"))
    s.MO = _add(db, WorkspaceMember(workspace_id=s.W1.id, user_id=s.UO.id, role="owner", status="active"))
    s.M2 = _add(db, WorkspaceMember(workspace_id=s.W2.id, user_id=s.U2.id, role="owner", status="active"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def member(db, S, U, role, status="active", ws=None):
    """Given `member(U, role, status="active", ws=W1)`; flushed."""
    ws = S.W1 if ws is None else ws
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status))


def token(db, S, R, **over):
    """Given `token K (R)`; `over` = the columns named after "but"; flushed."""
    fields = {
        "user_id": S.UA.id,
        "token_hash": hash_refresh_token(R),
        "family_id": S.FAM1,
        "workspace_id": None,
        "expires_at": LATER,
    }
    fields.update(over)
    return _add(db, RefreshToken(**fields))


def invitation(db, S, J, e, **over):
    """Given `invitation J to e` (J = the row's Given name, e.g. "I1"); flushed."""
    fields = {
        "workspace_id": S.W1.id,
        "email": e,
        "role": "member",
        "position": None,
        "token": f"inv-{J}-{S.TAG}",
        "status": "pending",
        "expires_at": FAR,
        "invited_by_user_id": S.UO.id,
    }
    fields.update(over)
    return _add(db, WorkspaceInvitation(**fields))


def PD(db, S):
    """Given `PD`: the default active plan with max_members=3."""
    return make_subscription_plan(db, name=f"free-{S.TAG}", is_default=True, is_active=True, max_members=3)


def limit(db, S, n):
    """Given `limit n`."""
    S.PL1.max_members = n
    db.flush()


def extra_row(db, S):
    """Given `extra row X` (after the commit point): returns (X, X_ID); not committed."""
    X = WorkspaceMember(workspace_id=S.W2.id, user_id=S.UQ.id, role="viewer", status="active")
    db.add(X)
    db.flush()
    return X, X.id


# --------------------------------------------------------------------------- #
# Conventions -> default_lifetimes (token lifetimes at the spec defaults)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def default_lifetimes(monkeypatch):
    """The spec states ACCESS_TOKEN_EXPIRE_MINUTES = 15 and
    REFRESH_TOKEN_EXPIRE_DAYS = 14 (the defaults); the dev `.env` loaded by
    `settings` sets 30 / 7. Pinned here so EXP15, NOW14, 900 and 1 209 600
    hold; cards that change a lifetime (AUTH-TP-09) set it again."""
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 14)


# --------------------------------------------------------------------------- #
# Conventions -> externals
# --------------------------------------------------------------------------- #


@contextmanager
def clock():
    """Convention **clock**: the four utcnow patches, all returning NOW."""
    with ExitStack() as st:
        for target in (
            "app.services.auth_service.utcnow",
            "app.core.security.utcnow",
            "app.dao.refresh_token.utcnow",
            "app.managers.workspace_manager.utcnow",
        ):
            st.enter_context(patch(target, return_value=NOW))
        yield


@contextmanager
def failing_issue():
    """Convention **failing issue** (AUTH-LI-13, SW-14): clock, but the access-token
    clock `app.core.security.utcnow` raises RuntimeError("clock down")."""
    with ExitStack() as st:
        for target in (
            "app.services.auth_service.utcnow",
            "app.dao.refresh_token.utcnow",
            "app.managers.workspace_manager.utcnow",
        ):
            st.enter_context(patch(target, return_value=NOW))
        st.enter_context(
            patch("app.core.security.utcnow", side_effect=RuntimeError("clock down"))
        )
        yield


@pytest.fixture
def dr(monkeypatch):
    """Convention **dr** (every ME card): Cloudinary delete patched, stamp settings set."""
    for name, value in (
        ("CLOUDINARY_UPLOAD_ENV", "development"),
        ("ENVIRONMENT", "development"),
        ("CLOUDINARY_CLOUD_NAME", "demo-cloud"),
        ("CLOUDINARY_API_KEY", "123456"),
        ("CLOUDINARY_API_SECRET", "s3cret"),
    ):
        monkeypatch.setattr(settings, name, value)
    with patch(
        "app.managers.profile_stamp_manager.destroy_resource",
        return_value={"result": "ok"},
    ) as m:
        yield m


@contextmanager
def spies(db):
    """Convention **spies**: yields (cm, rb)."""
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def claims(t):
    return jwt.decode(t, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False})


def row_of(db, p):
    db.expire_all()
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(p.refresh_token)))


def tokens(db, U):
    return db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == U.id))


def live(db, U):
    return db.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == U.id, RefreshToken.revoked_at.is_(None))
    )


def msgs(m):
    return [(x.type.value, x.message) for x in m]


def reread(db, model, id_):
    """Convention **re-read X**."""
    db.expire_all()
    return db.get(model, id_)


def snap(db, obj):
    """Column values of `obj` from the database (for **unchanged(X)**)."""
    model = type(obj)
    db.expire_all()
    row = db.get(model, obj.id)
    return {c.key: getattr(row, c.key) for c in sa_inspect(model).mapper.column_attrs}


_COUNTED = (Profile, Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceAuditLog, RefreshToken)


def counts(db):
    """Row counts for **nothing written** (all workspaces)."""
    return {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in _COUNTED}


def commit_point(db, *objs):
    """Convention **commit point**: `db.commit()`, then the snapshots.

    Returns (counts, {obj: snap}) — use `before["n"]` / `before[obj]`.
    """
    db.commit()
    snaps = {"n": counts(db)}
    for o in objs:
        snaps[o] = snap(db, o)
    return snaps


def audit(db, W, a):
    db.expire_all()
    return list(
        db.scalars(
            select(WorkspaceAuditLog)
            .where(WorkspaceAuditLog.workspace_id == W.id, WorkspaceAuditLog.action == a)
            .order_by(WorkspaceAuditLog.id)
        )
    )


def profile(db, e):
    db.expire_all()
    return db.scalar(select(Profile).where(Profile.email == e))


def count_ci(db, e):
    return db.scalar(select(func.count()).select_from(Profile).where(func.lower(Profile.email) == e.lower()))


def not_expired(o):
    return not (sa_inspect(o).expired_attributes & {c.key for c in sa_inspect(type(o)).mapper.column_attrs})


def x_count(db, X_ID):
    """x_kept = `x_count(db, X_ID) == 1`; x_gone = `== 0`."""
    return db.scalar(select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.id == X_ID))


class Recorder:
    """Convention **recorder**: `rec = Recorder(db)` as the last Given step,
    `rec.stop()` right after the When; `rec.inserts("profiles")`."""

    def __init__(self, db):
        self.stmts = []
        self.conn = db.connection()
        event.listen(self.conn, "before_cursor_execute", self._rec)

    def _rec(self, conn, cursor, statement, params, context, executemany):
        self.stmts.append(statement)

    def stop(self):
        event.remove(self.conn, "before_cursor_execute", self._rec)

    def inserts(self, t):
        return [s for s in self.stmts if s.startswith(f"INSERT INTO {t}")]


# =========================================================================== #
# Tests (card order)
# =========================================================================== #


# --------------------------------------------------------------------------- #
# Part A
# --------------------------------------------------------------------------- #
BUG_1860 = "BUG-1860: An email identifies one account only with its exact capitals"
BUG_1861 = "BUG-1861: Account email stored with the capitals typed"
BUG_1862 = "BUG-1862: Two accounts can hold the same email in other capitals"
BUG_1874 = "BUG-1874: Accepting one invitation leaves the other invitations to that email pending and counted"
BUG_1987 = "BUG-1987: Invitation expiry boundary differs from the lists and seat count"
BUG_2563 = "BUG-2563: Registration's workspace and invitation audit rows never carry client IP and user agent"
BUG_2564 = "BUG-2564: Two registrations of one email at once: the second answers 500 with SQL text"
BUG_2566 = "BUG-2566: A Bengali, symbol-only or long workspace name makes registration fail"
BUG_2567 = "BUG-2567: A second company with the same workspace name cannot register"


def a_rows(db, model, *where):
    """Rows of `model` matching `where`, freshly read, ordered by id."""
    db.expire_all()
    return list(db.scalars(select(model).where(*where).order_by(model.id)))


def a_slug_count(db, slug):
    return db.scalar(select(func.count()).select_from(Workspace).where(Workspace.slug == slug))


# =========================================================================== #
# AuthService._issue_token_pair
# =========================================================================== #


def test_auth_tp_01__access_token_claims(db, S):
    """AUTH-TP-01 — the access token names the user, the email and the workspace.
    Rules: _issue_token_pair R1."""
    # [claude] AUTH-TP-01
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=S.W1.id, family_id=None, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert isinstance(pair, TokenPair)
    # Then 2
    assert claims(pair.access_token)["sub"] == str(S.UA.id)
    # Then 3
    assert claims(pair.access_token)["email"] == S.EA
    # Then 4
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    # Then 5
    assert claims(pair.access_token)["exp"] == EXP15


def test_auth_tp_02__no_workspace_no_claim(db, S):
    """AUTH-TP-02 — no workspace gives no workspace_id claim.
    Rules: _issue_token_pair R1."""
    # [claude] AUTH-TP-02
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert "workspace_id" not in claims(pair.access_token)
    # Then 2
    assert claims(pair.access_token)["sub"] == str(S.UA.id)
    # Then 3
    assert row_of(db, pair).workspace_id is None


def test_auth_tp_03__refresh_row_stores_hash_and_diagnostics(db, S):
    """AUTH-TP-03 — one refresh row stores the hash and the diagnostics as given.
    Rules: _issue_token_pair R2."""
    # [claude] AUTH-TP-03
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=S.W1.id, family_id=None, user_agent=AGENT, ip_address="203.0.113.7, 10.0.0.1")
    # Then 1
    assert isinstance(pair.refresh_token, str)
    # Then 2
    assert row_of(db, pair) is not None
    assert row_of(db, pair).user_id == S.UA.id
    assert row_of(db, pair).workspace_id == S.W1.id
    # Then 3
    assert row_of(db, pair).expires_at == NOW14
    # Then 4
    assert row_of(db, pair).user_agent == "Mozilla/5.0 Test"
    assert row_of(db, pair).ip_address == "203.0.113.7, 10.0.0.1"
    # Then 5
    assert row_of(db, pair).revoked_at is None
    assert row_of(db, pair).replaced_by_id is None
    # Then 6
    assert tokens(db, S.UA) == 1


def test_auth_tp_04__given_family_joined(db, S):
    """AUTH-TP-04 — a given family is joined.
    Rules: _issue_token_pair R3."""
    # [claude] AUTH-TP-04
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=S.FAM1, user_agent=None, ip_address=None)
    # Then 1
    assert isinstance(pair, TokenPair)
    # Then 2
    assert row_of(db, pair).family_id == S.FAM1
    # Then 3
    assert row_of(db, pair).user_agent is None
    assert row_of(db, pair).ip_address is None


def test_auth_tp_05__family_none_new_hex_family(db, S):
    """AUTH-TP-05 — family None starts a new 32-hex family.
    Rules: _issue_token_pair R3."""
    # [claude] AUTH-TP-05
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert isinstance(pair, TokenPair)
    # Then 2
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_tp_06__empty_family_new_family(db, S):
    """AUTH-TP-06 — an empty family starts a new family too.
    Rules: _issue_token_pair R3."""
    # [claude] AUTH-TP-06
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id="", user_agent=None, ip_address=None)
    # Then 1
    assert isinstance(pair, TokenPair)
    # Then 2
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_tp_07__two_calls_two_tokens_rows_families(db, S):
    """AUTH-TP-07 — two calls give two tokens, two rows and two families.
    Rules: _issue_token_pair R3, R4."""
    # [claude] AUTH-TP-07
    with clock():
        first = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert pair.refresh_token != first.refresh_token
    # Then 2
    assert tokens(db, S.UA) == 2
    # Then 3
    assert row_of(db, pair).family_id != row_of(db, first).family_id


def test_auth_tp_08__lifetimes_900_and_1209600(db, S):
    """AUTH-TP-08 — the lifetimes are 900 and 1 209 600 seconds.
    Rules: _issue_token_pair R4."""
    # [claude] AUTH-TP-08
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert pair.expires_in == 900
    # Then 2
    assert pair.refresh_expires_in == 1209600


def test_auth_tp_09__lifetimes_read_at_call_time(db, S, monkeypatch):
    """AUTH-TP-09 — the lifetimes are read from the settings at call time.
    Rules: _issue_token_pair R2, R4; R1 (exp)."""
    # [claude] AUTH-TP-09
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert pair.expires_in == 1800
    # Then 2
    assert pair.refresh_expires_in == 604800
    # Then 3
    assert claims(pair.access_token)["exp"] == int(datetime(2026, 3, 5, 12, 30, 0, tzinfo=timezone.utc).timestamp())
    # Then 4
    assert row_of(db, pair).expires_at == NOW + timedelta(days=7)


def test_auth_tp_10__raw_refresh_token_stored_nowhere(db, S):
    """AUTH-TP-10 — the raw refresh token is stored nowhere.
    Rules: _issue_token_pair R5."""
    # [claude] AUTH-TP-10
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=S.W1.id, family_id=None, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert len(pair.refresh_token) > 0
    # Then 2
    assert row_of(db, pair).token_hash == hash_refresh_token(pair.refresh_token)
    # Then 3
    row = row_of(db, pair)
    assert pair.refresh_token not in [str(getattr(row, c.key)) for c in sa_inspect(RefreshToken).mapper.column_attrs]


def test_auth_tp_11__flushed_never_committed(db, S):
    """AUTH-TP-11 — the refresh row is flushed, never committed.
    Rules: _issue_token_pair Returns."""
    # [claude] AUTH-TP-11
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock():
            svc._issue_token_pair(db, user=S.UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert tokens(db, S.UA) == 1
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert tokens(db, S.UA) == 0


def test_auth_tp_12__workspace_id_zero_fails_at_flush(db, S):
    """AUTH-TP-12 — workspace id 0 fails at the flush and returns no pair.
    Rules: _issue_token_pair R1a."""
    # [claude] AUTH-TP-12
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock():
                svc._issue_token_pair(db, user=S.UA, workspace_id=0, family_id=None, user_agent=None, ip_address=None)
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_tp_13__workspace_id_zero_present_in_claims(db, S, monkeypatch):
    """AUTH-TP-13 — workspace id 0 is present in the claims.
    Rules: _issue_token_pair R1, R1a (the `0 is present` boundary)."""
    # [claude] AUTH-TP-13
    fake = SimpleNamespace(create=lambda *a, **k: None)
    monkeypatch.setattr(auth_service, "refresh_token_dao", fake)
    with clock():
        pair = svc._issue_token_pair(db, user=S.UA, workspace_id=0, family_id=None, user_agent=None, ip_address=None)
    # Then 1
    assert "workspace_id" in claims(pair.access_token)
    # Then 2
    assert claims(pair.access_token)["workspace_id"] == 0


# =========================================================================== #
# AuthService.register_user
# =========================================================================== #


def test_auth_rg_01__workspace_name_creates_account_workspace_session(db, S):
    """AUTH-RG-01 — a workspace name creates the account, the workspace and the session.
    Rules: register_user R3, R6; _register_with_new_workspace R3."""
    # [claude] AUTH-RG-01
    PD(db, S)
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, invitation_token=None, timezone="Asia/Dhaka", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert user.email == S.EN
    assert user.name == "Nia New"
    # Then 2
    assert ws.name == S.WSNAME
    assert ws.slug == S.SL
    db.rollback()
    # Then 3
    assert profile(db, S.EN) is not None
    assert profile(db, S.EN).timezone == "Asia/Dhaka"
    # Then 4
    wss = a_rows(db, Workspace, Workspace.slug == S.SL)
    assert len(wss) == 1
    assert wss[0].owner_user_id == user.id
    # Then 5
    mem = a_rows(db, WorkspaceMember, WorkspaceMember.workspace_id == ws.id)
    assert len(mem) == 1
    assert mem[0].user_id == user.id
    assert mem[0].role == "owner"
    assert mem[0].status == "active"
    # Then 6
    assert tokens(db, user) == 1


def test_auth_rg_02__new_workspace_messages_then_welcome(db, S):
    """AUTH-RG-02 — new-workspace messages, then the welcome message.
    Rules: register_user R5; _register_with_new_workspace R1."""
    # [claude] AUTH-RG-02
    PD(db, S)
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, timezone=None)
    # Then 1
    assert msgs(messages) == [
        ("success", "User profile created"),
        ("success", f"Workspace '{S.WSNAME}' created successfully with 14-day trial"),
        ("success", "Welcome Nia New! Your account has been created successfully."),
    ]


def test_auth_rg_03__one_commit_rows_reread(db, S):
    """AUTH-RG-03 — one commit, and the returned rows are re-read.
    Rules: register_user R6 (TC1, TC2)."""
    # [claude] AUTH-RG-03
    PD(db, S)
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert not_expired(user)
    # Then 2
    assert not_expired(ws)
    # Then 3
    assert cm.call_count == 1
    # Then 4
    assert rb.call_count == 0


def test_auth_rg_04__taken_email_refused_rolled_back(db, S):
    """AUTH-RG-04 — a taken email is refused, rolled back, and pending changes are discarded.
    Rules: register_user R1, R7 (TC3)."""
    # [claude] AUTH-RG-04
    PD(db, S)
    before = commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.register_user(db, name="Ann Again", email=S.EA, password=PW, workspace_name=S.WSNAME)
    assert str(exc.value) == TAKEN
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert counts(db) == before["n"]
    # Then 5
    assert count_ci(db, S.EA) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_auth_rg_05__other_capitals_same_account(db, S):
    """AUTH-RG-05 — an email in other capitals is the same account.
    Rules: register_user R1a [BUG-1860]."""
    # [claude] AUTH-RG-05
    make_profile(db, email=S.MIXED, name="Ann Mixed")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.register_user(db, name="Ann Again", email=S.LOWER, password=PW)
    assert str(exc.value) == TAKEN
    # Then 2
    assert count_ci(db, S.LOWER) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_auth_rg_06__argument_capitals_find_lower_account(db, S):
    """AUTH-RG-06 — capitals on the argument side find a lower-case account.
    Rules: register_user R1a [BUG-1860]."""
    # [claude] AUTH-RG-06
    make_profile(db, email=S.LOWER, name="Ann Lower")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.register_user(db, name="Ann Again", email=S.UPPER, password=PW)
    assert str(exc.value) == TAKEN
    # Then 2
    assert count_ci(db, S.LOWER) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_auth_rg_07__outer_spaces_around_taken_email(db, S):
    """AUTH-RG-07 — outer spaces around a taken email are ignored.
    Rules: register_user R1a [BUG-1860]."""
    # [claude] AUTH-RG-07
    make_profile(db, email=S.LOWER, name="Ann Lower")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.register_user(db, name="Ann Again", email=f"  {S.LOWER} ", password=PW)
    assert str(exc.value) == TAKEN
    # Then 2
    assert count_ci(db, S.LOWER) == 1


def test_auth_rg_08__different_inner_text_not_taken(db, S):
    """AUTH-RG-08 — a different inner text is not taken.
    Rules: register_user R1, R1a (inner text still counts)."""
    # [claude] AUTH-RG-08
    make_profile(db, email=S.LOWER, name="Ann Lower")
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Ann Lea", email=f"ann.lea.{S.TAG}@example.com", password=PW)
    # Then 1
    assert user.email == f"ann.lea.{S.TAG}@example.com"
    db.rollback()
    # Then 2
    assert count_ci(db, S.LOWER) == 1
    # Then 3
    assert count_ci(db, f"ann.lea.{S.TAG}@example.com") == 1


@pytest.mark.xfail(strict=True, reason=BUG_1861)
def test_auth_rg_09__new_email_stored_lower_cased(db, S):
    """AUTH-RG-09 — a new account's email is stored lower-cased.
    Rules: register_user R1a [BUG-1861]."""
    # [claude] AUTH-RG-09
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Ann Lee", email=S.MIXED, password=PW)
    db.rollback()
    # Then 1
    assert count_ci(db, S.MIXED) == 1
    # Then 2
    assert profile(db, S.LOWER) is not None


def test_auth_rg_10__mixed_case_email_one_account(db, S):
    """AUTH-RG-10 — a mixed-case email registers one account.
    Rules: register_user R1a (part independent of BUG-1861), R4."""
    # [claude] AUTH-RG-10
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Ann Lee", email=S.MIXED, password=PW)
    # Then 1
    assert user.email.lower() == S.LOWER
    db.rollback()
    # Then 2
    assert count_ci(db, S.MIXED) == 1


@pytest.mark.xfail(strict=True, reason=BUG_2564)
def test_auth_rg_11__race_loser_gets_normal_refusal(db, S):
    """AUTH-RG-11 — two registrations at once: the loser gets the normal refusal.
    Rules: register_user R1b [BUG-2564]."""
    # [claude] AUTH-RG-11
    PD(db, S)
    before = commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with patch.object(DAOProfile, "get_by_email", return_value=None):
            with spies(db) as (cm, rb), clock():
                svc.register_user(db, name="Ann Again", email=S.EA, password=PW, workspace_name=S.WSNAME)
    assert str(exc.value) == TAKEN
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert counts(db) == before["n"]


def test_auth_rg_12__race_insert_reaches_index_nothing_stays(db, S):
    """AUTH-RG-12 — under the race, the insert reaches the index and nothing stays.
    Rules: register_user R1b, R7 (holds today and after BUG-2564)."""
    # [claude] AUTH-RG-12
    PD(db, S)
    before = commit_point(db)
    rec = Recorder(db)
    with patch.object(DAOProfile, "get_by_email", return_value=None):
        with pytest.raises(Exception):  # noqa: B017  (card: any error; RG-12 checks what reached the database)
            with clock():
                svc.register_user(db, name="Ann Again", email=S.EA, password=PW, workspace_name=S.WSNAME)
    rec.stop()
    # Then 1
    assert len(rec.inserts("profiles")) == 1
    # Then 2
    assert count_ci(db, S.EA) == 1
    # Then 3
    assert a_slug_count(db, S.SL) == 0
    # Then 4
    assert counts(db) == before["n"]


@pytest.mark.xfail(strict=True, reason=BUG_1862)
def test_auth_rg_13__case_variant_past_check_refused_by_db(db, S):
    """AUTH-RG-13 — a case variant past the check is refused by the database, as a normal refusal.
    Rules: register_user R1a [BUG-1862], R1b [BUG-2564]."""
    # [claude] AUTH-RG-13
    make_profile(db, email=S.MIXED, name="Ann Mixed")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with patch.object(DAOProfile, "get_by_email", return_value=None):
            with clock():
                svc.register_user(db, name="Ann Again", email=S.LOWER, password=PW)
    assert str(exc.value) == TAKEN
    # Then 2
    assert count_ci(db, S.LOWER) == 1


def test_auth_rg_14__token_and_workspace_name_token_wins(db, S):
    """AUTH-RG-14 — a token and a workspace name: the token wins.
    Rules: register_user R2."""
    # [claude] AUTH-RG-14
    PD(db, S)
    invitation(db, S, "I", S.EN)
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert ws.id == S.W1.id
    db.rollback()
    # Then 2
    assert a_slug_count(db, S.SL) == 0
    # Then 3
    mem = a_rows(db, WorkspaceMember, WorkspaceMember.workspace_id == S.W1.id, WorkspaceMember.user_id == user.id)
    assert len(mem) == 1
    assert mem[0].role == "member"
    assert mem[0].status == "active"


def test_auth_rg_15__empty_token_takes_workspace_path(db, S):
    """AUTH-RG-15 — an empty token with a workspace name takes the workspace path.
    Rules: register_user R2, R3."""
    # [claude] AUTH-RG-15
    PD(db, S)
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, invitation_token="")
    # Then 1
    assert ws.slug == S.SL
    db.rollback()
    # Then 2
    assert a_slug_count(db, S.SL) == 1


def test_auth_rg_16__neither_token_nor_name_account_only(db, S):
    """AUTH-RG-16 — neither a token nor a name: an account without a workspace.
    Rules: register_user R4, R5."""
    # [claude] AUTH-RG-16
    before = commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=None, invitation_token=None)
    # Then 1
    assert ws is None
    # Then 2
    assert msgs(messages) == [
        ("success", "User profile created"),
        ("success", "Welcome Nia New! Your account has been created successfully."),
    ]
    db.rollback()
    # Then 3
    assert profile(db, S.EN) is not None
    # Then 4
    assert counts(db)["workspaces"] == before["n"]["workspaces"]
    # Then 5
    assert a_rows(db, WorkspaceMember, WorkspaceMember.user_id == user.id) == []


def test_auth_rg_17__empty_strings_account_only(db, S):
    """AUTH-RG-17 — empty strings for both take the account-only path.
    Rules: register_user R4."""
    # [claude] AUTH-RG-17
    before = commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name="", invitation_token="")
    # Then 1
    assert ws is None
    # Then 2
    assert counts(db)["workspaces"] == before["n"]["workspaces"]


def test_auth_rg_18__invitation_messages_then_welcome(db, S):
    """AUTH-RG-18 — invitation messages, then the welcome message.
    Rules: register_user R5; _register_with_invitation R2."""
    # [claude] AUTH-RG-18
    invitation(db, S, "I", S.EN)
    commit_point(db)
    with clock():
        user, ws, pair, messages = svc.register_user(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert msgs(messages) == [
        ("info", "Valid invitation found for workspace: Acme Works"),
        ("success", "User profile created"),
        ("success", "You've been added to workspace 'Acme Works' with role 'member'"),
        ("success", "Welcome Nia New! Your account has been created successfully."),
    ]


def test_auth_rg_19__no_default_plan_refused_rolled_back(db, S):
    """AUTH-RG-19 — no default plan: refused, the account is rolled back, pending changes discarded.
    Rules: register_user R7 (TC3); _register_with_new_workspace R4, Errors "no default plan"."""
    # [claude] AUTH-RG-19
    before = commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    assert str(exc.value) == "No default subscription plan found"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert counts(db) == before["n"]


def test_auth_rg_20__invalid_time_zone_validation_error(db, S):
    """AUTH-RG-20 — an invalid time zone is a validation error and nothing stays.
    Rules: register_user R7 (TC3); _register_user_only R1."""
    # [claude] AUTH-RG-20
    PD(db, S)
    before = commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(PydanticValidationError):
        with clock():
            svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, timezone="Mars/Base")
    # Then 2
    assert x_count(db, X_ID) == 0
    # Then 3
    assert counts(db) == before["n"]


def test_auth_rg_21__full_workspace_refuses_invited_registration(db, S):
    """AUTH-RG-21 — a full workspace refuses the invited registration and removes the account.
    Rules: register_user R7; _register_with_invitation R6."""
    # [claude] AUTH-RG-21
    limit(db, S, 1)
    inv = invitation(db, S, "I", S.EN)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.register_user(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."
    # Then 2
    assert profile(db, S.EN) is None
    # Then 3
    assert reread(db, WorkspaceInvitation, inv.id).status == "pending"
    # Then 4
    assert counts(db) == before["n"]


def test_auth_rg_22__failing_commit_saves_nothing(db, S):
    """AUTH-RG-22 — a failing commit saves nothing.
    Rules: register_user R7 (TC4)."""
    # [claude] AUTH-RG-22
    PD(db, S)
    before = commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:
            with clock():
                svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert profile(db, S.EN) is None
    # Then 4
    assert counts(db) == before["n"]


def test_auth_rg_23__failing_reread_keeps_account(db, S):
    """AUTH-RG-23 — a failing re-read after the commit keeps the account.
    Rules: register_user R7 (TC5)."""
    # [claude] AUTH-RG-23
    PD(db, S)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            with clock():
                svc.register_user(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert profile(db, S.EN) is not None
    # Then 3
    assert a_slug_count(db, S.SL) == 1


# =========================================================================== #
# AuthService._register_user_only
# =========================================================================== #


def test_auth_ru_01__account_hashed_password_email_user_id(db, S):
    """AUTH-RU-01 — the account is created with a hashed password and the email as user_id.
    Rules: _register_user_only R1, Returns."""
    # [claude] AUTH-RU-01
    with clock():
        user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=S.EN, password=PW, timezone="Asia/Dhaka", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws is None
    # Then 2
    assert msgs(messages) == [("success", "User profile created")]
    # Then 3
    row = reread(db, Profile, user.id)
    assert row.email == S.EN
    assert row.name == "Nia New"
    assert row.timezone == "Asia/Dhaka"
    assert row.user_id == S.EN
    # Then 4
    assert verify_password(PW, row.hashed_password) is True


def test_auth_ru_02__session_no_workspace_new_family(db, S):
    """AUTH-RU-02 — the session has no workspace and a new family.
    Rules: _register_user_only R2."""
    # [claude] AUTH-RU-02
    with clock():
        user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=S.EN, password=PW, timezone=None, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert "workspace_id" not in claims(pair.access_token)
    # Then 2
    assert claims(pair.access_token)["sub"] == str(user.id)
    # Then 3
    assert row_of(db, pair).workspace_id is None
    assert row_of(db, pair).user_agent == "Mozilla/5.0 Test"
    assert row_of(db, pair).ip_address == "203.0.113.7"
    # Then 4
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_ru_03__no_workspace_membership_or_audit(db, S):
    """AUTH-RU-03 — no workspace, membership or audit row is written.
    Rules: _register_user_only R3."""
    # [claude] AUTH-RU-03
    before = commit_point(db)
    with clock():
        user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=S.EN, password=PW)
    # Then 1
    assert ws is None
    # Then 2
    after = counts(db)
    for t in ("workspaces", "workspace_members", "workspace_audit_logs"):
        assert after[t] == before["n"][t]
    # Then 3
    assert tokens(db, user) == 1


def test_auth_ru_04__whitespace_time_zone_stored_none(db, S):
    """AUTH-RU-04 — a whitespace time zone is stored as None.
    Rules: _register_user_only R1 (blank time zone -> None)."""
    # [claude] AUTH-RU-04
    with clock():
        user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=S.EN, password=PW, timezone="   ")
    # Then 1
    assert user.email == S.EN
    # Then 2
    assert reread(db, Profile, user.id).timezone is None


def test_auth_ru_05__invalid_time_zone_raises_before_writes(db, S):
    """AUTH-RU-05 — an invalid time zone raises before anything is written.
    Rules: _register_user_only R1, Errors."""
    # [claude] AUTH-RU-05
    before = commit_point(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        with clock():
            svc._register_user_only(db, name="Nia New", email=S.EN, password=PW, timezone="Mars/Base")
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db) == before["n"]


def test_auth_ru_06__flushed_never_committed(db, S):
    """AUTH-RU-06 — flushed, never committed.
    Rules: _register_user_only Returns (flushed)."""
    # [claude] AUTH-RU-06
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock():
            user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=S.EN, password=PW)
    # Then 1
    assert profile(db, S.EN) is not None
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert profile(db, S.EN) is None


# =========================================================================== #
# AuthService._register_with_invitation
# =========================================================================== #


def test_auth_ri_01__joins_with_invitation_role_and_position(db, S):
    """AUTH-RI-01 — the invited account joins with the invitation's role and position.
    Rules: _register_with_invitation R3, Returns."""
    # [claude] AUTH-RI-01
    inv = invitation(db, S, "I", S.EN, role="viewer", position="Supervisor")
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.id == S.W1.id
    assert user.email == S.EN
    # Then 2
    mem = a_rows(db, WorkspaceMember, WorkspaceMember.workspace_id == S.W1.id, WorkspaceMember.user_id == user.id)
    assert len(mem) == 1
    # Then 3
    row = reread(db, WorkspaceMember, mem[0].id)
    assert row.role == "viewer"
    assert row.position == "Supervisor"
    assert row.status == "active"
    # Then 4
    i = reread(db, WorkspaceInvitation, inv.id)
    assert i.status == "accepted"
    assert i.accepted_by_user_id == user.id
    assert i.accepted_at == NOW


def test_auth_ri_02__messages_found_profile_added(db, S):
    """AUTH-RI-02 — messages: invitation found, profile, added with the role.
    Rules: _register_with_invitation R2."""
    # [claude] AUTH-RI-02
    invitation(db, S, "I", S.EN, role="viewer")
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert msgs(messages) == [
        ("info", "Valid invitation found for workspace: Acme Works"),
        ("success", "User profile created"),
        ("success", "You've been added to workspace 'Acme Works' with role 'viewer'"),
    ]


def test_auth_ri_03__session_for_invitation_workspace(db, S):
    """AUTH-RI-03 — the session is for the invitation's workspace, in a new family.
    Rules: _register_with_invitation R5."""
    # [claude] AUTH-RI-03
    invitation(db, S, "I", S.EN)
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    # Then 2
    assert row_of(db, pair).workspace_id == S.W1.id
    assert row_of(db, pair).user_id == user.id
    # Then 3
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_ri_04__accept_writes_member_added_and_accepted(db, S):
    """AUTH-RI-04 — the accept writes member_added and invitation_accepted.
    Rules: _register_with_invitation R3."""
    # [claude] AUTH-RI-04
    inv = invitation(db, S, "I", S.EN, role="viewer")
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    added = audit(db, S.W1, "member_added")
    assert len(added) == 1
    # Then 3
    assert added[0].user_id == S.UO.id
    assert added[0].metadata_json == {"new_member_id": user.id, "role": "viewer"}
    # Then 4
    accepted = audit(db, S.W1, "invitation_accepted")
    assert len(accepted) == 1
    # Then 5
    assert accepted[0].user_id == user.id
    assert accepted[0].metadata_json == {"invitation_id": inv.id}


@pytest.mark.xfail(strict=True, reason=BUG_2563)
def test_auth_ri_05__accept_audit_rows_carry_client(db, S):
    """AUTH-RI-05 — the accept's audit rows carry the client's address and browser.
    Rules: _register_with_invitation R4 [BUG-2563]."""
    # [claude] AUTH-RI-05
    invitation(db, S, "I", S.EN)
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}", user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    added = audit(db, S.W1, "member_added")
    assert len(added) == 1
    # Then 3
    assert added[0].ip_address == "203.0.113.7"
    assert added[0].user_agent == "Mozilla/5.0 Test"
    # Then 4
    accepted = audit(db, S.W1, "invitation_accepted")
    assert accepted[0].ip_address == "203.0.113.7"
    assert accepted[0].user_agent == "Mozilla/5.0 Test"


def test_auth_ri_06__unknown_token_refused(db, S):
    """AUTH-RI-06 — an unknown token is refused before anything is written.
    Rules: _register_with_invitation R1, Errors."""
    # [claude] AUTH-RI-06
    invitation(db, S, "I", S.EN)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-Z-{S.TAG}")
    assert str(exc.value) == "Invalid invitation token"
    # Then 2
    assert not db.new and not db.dirty
    # Then 3
    assert counts(db) == before["n"]


def test_auth_ri_07__token_in_capitals_unknown(db, S):
    """AUTH-RI-07 — the token in capitals is unknown.
    Rules: _register_with_invitation R1 (exact token)."""
    # [claude] AUTH-RI-07
    invitation(db, S, "I", S.EN)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"INV-I-{S.TAG.upper()}")
    assert str(exc.value) == "Invalid invitation token"
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_08__token_with_leading_space_unknown(db, S):
    """AUTH-RI-08 — the token with a leading space is unknown.
    Rules: _register_with_invitation R1 (exact token)."""
    # [claude] AUTH-RI-08
    invitation(db, S, "I", S.EN)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f" inv-I-{S.TAG}")
    assert str(exc.value) == "Invalid invitation token"
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_09__expired_invitation_refused(db, S):
    """AUTH-RI-09 — an expired invitation is refused.
    Rules: _register_with_invitation R1."""
    # [claude] AUTH-RI-09
    invitation(db, S, "I", S.EN, expires_at=NOW - US)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == EXPIRED_INV
    # Then 2
    assert counts(db) == before["n"]


@pytest.mark.xfail(strict=True, reason=BUG_1987)
def test_auth_ri_10__expiring_exactly_now_is_expired(db, S):
    """AUTH-RI-10 — an invitation expiring exactly now is expired.
    Rules: _register_with_invitation R1 (BUG-1987 of the manager)."""
    # [claude] AUTH-RI-10
    invitation(db, S, "I", S.EN, expires_at=NOW)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == EXPIRED_INV
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_11__one_microsecond_from_expiry_accepted(db, S):
    """AUTH-RI-11 — an invitation one microsecond from expiry is accepted.
    Rules: _register_with_invitation R1."""
    # [claude] AUTH-RI-11
    inv = invitation(db, S, "I", S.EN, expires_at=NOW + US)
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    assert reread(db, WorkspaceInvitation, inv.id).status == "accepted"


def test_auth_ri_12__accepted_invitation_cannot_be_reused(db, S):
    """AUTH-RI-12 — an accepted invitation cannot be used again.
    Rules: _register_with_invitation R1."""
    # [claude] AUTH-RI-12
    invitation(db, S, "I", S.EN, status="accepted")
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Invitation has already been accepted"
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_13__cancelled_invitation_refused(db, S):
    """AUTH-RI-13 — a cancelled invitation is refused.
    Rules: _register_with_invitation R1."""
    # [claude] AUTH-RI-13
    invitation(db, S, "I", S.EN, status="cancelled")
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Invitation has already been cancelled"
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_14__invitation_to_other_email_refused(db, S):
    """AUTH-RI-14 — an invitation sent to another email is refused.
    Rules: _register_with_invitation R1."""
    # [claude] AUTH-RI-14
    invitation(db, S, "I", f"other.{S.TAG}@acme.com")
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == f"This invitation was sent to other.{S.TAG}@acme.com. You cannot accept it with {S.EN}."
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ri_15__invited_email_other_capitals_accepted(db, S):
    """AUTH-RI-15 — the invited email in other capitals is accepted.
    Rules: _register_with_invitation R1 (email ignoring capitals)."""
    # [claude] AUTH-RI-15
    invitation(db, S, "I", S.EN)
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=f"New.{S.TAG}@acme.com", password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    mem = a_rows(db, WorkspaceMember, WorkspaceMember.workspace_id == S.W1.id, WorkspaceMember.user_id == user.id)
    assert len(mem) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1874)
def test_auth_ri_16__other_pending_invitations_cancelled(db, S):
    """AUTH-RI-16 — other pending invitations to the same email are cancelled.
    Rules: _register_with_invitation R3 (BUG-1874 of the manager)."""
    # [claude] AUTH-RI-16
    inv_i = invitation(db, S, "I", S.EN)
    inv_j = invitation(db, S, "J", S.EN, role="viewer")
    with clock():
        user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert reread(db, WorkspaceInvitation, inv_i.id).status == "accepted"
    # Then 2
    assert reread(db, WorkspaceInvitation, inv_j.id).status == "cancelled"


def test_auth_ri_17__flushed_never_committed(db, S):
    """AUTH-RI-17 — flushed, never committed.
    Rules: _register_with_invitation Returns (flushed)."""
    # [claude] AUTH-RI-17
    inv = invitation(db, S, "I", S.EN)
    commit_point(db)
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock():
            user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=S.EN, password=PW, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert profile(db, S.EN) is not None
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert profile(db, S.EN) is None
    # Then 4
    assert reread(db, WorkspaceInvitation, inv.id).status == "pending"


# =========================================================================== #
# AuthService._register_with_new_workspace
# =========================================================================== #


def test_auth_rw_01__default_plan_and_billing_email(db, S):
    """AUTH-RW-01 — the workspace uses the default plan and the email for billing.
    Rules: _register_with_new_workspace R3, R4."""
    # [claude] AUTH-RW-01
    pd = PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.slug == S.SL
    assert ws.name == S.WSNAME
    # Then 2
    w = reread(db, Workspace, ws.id)
    assert w.subscription_plan_id == pd.id
    assert w.billing_email == S.EN
    assert w.owner_user_id == user.id
    # Then 3
    mem = a_rows(db, WorkspaceMember, WorkspaceMember.workspace_id == ws.id)
    assert len(mem) == 1
    # Then 4
    row = reread(db, WorkspaceMember, mem[0].id)
    assert row.user_id == user.id
    assert row.role == "owner"
    assert row.status == "active"
    assert row.position is None


def test_auth_rw_02__one_workspace_created_audit_names_plan(db, S):
    """AUTH-RW-02 — one workspace_created audit row names the plan.
    Rules: _register_with_new_workspace R4."""
    # [claude] AUTH-RW-02
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.slug == S.SL
    # Then 2
    rows = audit(db, ws, "workspace_created")
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == user.id
    assert rows[0].metadata_json == {"plan": f"free-{S.TAG}"}


@pytest.mark.xfail(strict=True, reason=BUG_2563)
def test_auth_rw_03__workspace_created_row_carries_client(db, S):
    """AUTH-RW-03 — the workspace_created row carries the client's address and browser.
    Rules: _register_with_new_workspace R5 [BUG-2563]."""
    # [claude] AUTH-RW-03
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.slug == S.SL
    # Then 2
    rows = audit(db, ws, "workspace_created")
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


def test_auth_rw_04__messages_profile_then_workspace(db, S):
    """AUTH-RW-04 — messages: profile, then workspace with the name as passed.
    Rules: _register_with_new_workspace R1."""
    # [claude] AUTH-RW-04
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"R&D Ltd. {S.TAG}")
    # Then 1
    assert msgs(messages) == [
        ("success", "User profile created"),
        ("success", f"Workspace 'R&D Ltd. {S.TAG}' created successfully with 14-day trial"),
    ]


def test_auth_rw_05__session_for_new_workspace(db, S):
    """AUTH-RW-05 — the session is for the new workspace.
    Rules: _register_with_new_workspace R6."""
    # [claude] AUTH-RW-05
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert claims(pair.access_token)["workspace_id"] == ws.id
    # Then 2
    assert row_of(db, pair).workspace_id == ws.id
    assert row_of(db, pair).user_id == user.id
    # Then 3
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_rw_06__seeded_departments(db, S):
    """AUTH-RW-06 — the new workspace gets its seeded departments.
    Rules: _register_with_new_workspace R4 (seeded data, manager R9)."""
    # [claude] AUTH-RW-06
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert ws.id is not None
    # Then 2
    assert db.scalar(text("SELECT count(*) FROM departments WHERE workspace_id = :w"), {"w": ws.id}) == 5


def test_auth_rw_07__spaces_underscores_become_dashes(db, S):
    """AUTH-RW-07 — spaces and underscores become dashes.
    Rules: _register_with_new_workspace R2."""
    # [claude] AUTH-RW-07
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"Acme Steel_Works {S.TAG}")
    # Then 1
    assert ws.slug == f"acme-steel-works-{S.TAG}"


def test_auth_rw_08__dash_runs_collapse_outer_dashes_go(db, S):
    """AUTH-RW-08 — runs of dashes collapse and outer dashes go.
    Rules: _register_with_new_workspace R2."""
    # [claude] AUTH-RW-08
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"  A -- B {S.TAG}  ")
    # Then 1
    assert ws.slug == f"a-b-{S.TAG}"
    # Then 2
    assert reread(db, Workspace, ws.id).name == f"  A -- B {S.TAG}  "


def test_auth_rw_09__symbols_dropped_name_as_typed(db, S):
    """AUTH-RW-09 — symbols are dropped, the name is stored as typed.
    Rules: _register_with_new_workspace R2."""
    # [claude] AUTH-RW-09
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"R&D Ltd. {S.TAG}")
    # Then 1
    assert ws.slug == f"rd-ltd-{S.TAG}"
    # Then 2
    assert reread(db, Workspace, ws.id).name == f"R&D Ltd. {S.TAG}"


def test_auth_rw_10__exactly_100_slug_characters_kept(db, S):
    """AUTH-RW-10 — a name of exactly 100 slug characters keeps them all.
    Rules: _register_with_new_workspace R2a (the edge that holds today)."""
    # [claude] AUTH-RW-10
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.TAG + "y" * 92)
    # Then 1
    assert ws.slug == S.TAG + "y" * 92
    # Then 2
    assert len(ws.slug) == 100


@pytest.mark.xfail(strict=True, reason=BUG_2566)
def test_auth_rw_11__non_ascii_digit_is_separator(db, S):
    """AUTH-RW-11 — a non-ASCII digit acts as a separator.
    Rules: _register_with_new_workspace R2a [BUG-2566]."""
    # [claude] AUTH-RW-11
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"Plant² Two {S.TAG}")
    # Then 1
    assert ws.slug == f"plant-two-{S.TAG}"
    # Then 2
    assert reread(db, Workspace, ws.id).name == f"Plant² Two {S.TAG}"


@pytest.mark.xfail(strict=True, reason=BUG_2566)
def test_auth_rw_12__bengali_letters_are_separators(db, S):
    """AUTH-RW-12 — Bengali letters act as separators.
    Rules: _register_with_new_workspace R2a [BUG-2566]."""
    # [claude] AUTH-RW-12
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=f"কারখানা {S.TAG}")
    # Then 1
    assert ws.slug == S.TAG


@pytest.mark.xfail(strict=True, reason=BUG_2566)
def test_auth_rw_13__no_ascii_letter_or_digit_slug_workspace(db, S):
    """AUTH-RW-13 — a name with no ASCII letter or digit gets the slug "workspace".
    Rules: _register_with_new_workspace R2a [BUG-2566]."""
    # [claude] AUTH-RW-13
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name="!!!")
    # Then 1
    assert re.fullmatch(r"workspace(-[0-9]+)?", ws.slug) is not None
    # Then 2
    assert reread(db, Workspace, ws.id).name == "!!!"


@pytest.mark.xfail(strict=True, reason=BUG_2566)
def test_auth_rw_14__long_name_cut_to_100(db, S):
    """AUTH-RW-14 — a long name is cut to 100 characters.
    Rules: _register_with_new_workspace R2a [BUG-2566]."""
    # [claude] AUTH-RW-14
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.TAG + "y" * 142)
    # Then 1
    assert ws.slug == S.TAG + "y" * 92


@pytest.mark.xfail(strict=True, reason=BUG_2566)
def test_auth_rw_15__cut_leaves_no_trailing_dash(db, S):
    """AUTH-RW-15 — the cut leaves no trailing dash.
    Rules: _register_with_new_workspace R2a [BUG-2566]."""
    # [claude] AUTH-RW-15
    PD(db, S)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.TAG + "y" * 91 + " " + "z" * 50)
    # Then 1
    assert ws.slug == S.TAG + "y" * 91


@pytest.mark.xfail(strict=True, reason=BUG_2567)
def test_auth_rw_16__taken_slug_gets_2(db, S):
    """AUTH-RW-16 — a taken slug gets -2.
    Rules: _register_with_new_workspace R3a [BUG-2567]."""
    # [claude] AUTH-RW-16
    PD(db, S)
    W3 = make_workspace(db, slug=S.SL)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert ws.slug == f"{S.SL}-2"
    # Then 2
    assert reread(db, Workspace, W3.id).slug == S.SL


@pytest.mark.xfail(strict=True, reason=BUG_2567)
def test_auth_rw_17__with_2_taken_3_used(db, S):
    """AUTH-RW-17 — with -2 taken too, -3 is used.
    Rules: _register_with_new_workspace R3a [BUG-2567]."""
    # [claude] AUTH-RW-17
    PD(db, S)
    make_workspace(db, slug=S.SL)
    make_workspace(db, slug=f"{S.SL}-2")
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert ws.slug == f"{S.SL}-3"


@pytest.mark.xfail(strict=True, reason=BUG_2567)
def test_auth_rw_18__taken_100_char_slug_cut_for_suffix(db, S):
    """AUTH-RW-18 — a taken 100-character slug is cut so that the suffix fits.
    Rules: _register_with_new_workspace R3a [BUG-2567]."""
    # [claude] AUTH-RW-18
    PD(db, S)
    make_workspace(db, slug=S.TAG + "y" * 92)
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.TAG + "y" * 92)
    # Then 1
    assert ws.slug == S.TAG + "y" * 90 + "-2"
    # Then 2
    assert len(ws.slug) == 100


def test_auth_rw_19__only_exact_slug_counts_as_taken(db, S):
    """AUTH-RW-19 — only the exact slug counts as taken.
    Rules: _register_with_new_workspace R3."""
    # [claude] AUTH-RW-19
    PD(db, S)
    make_workspace(db, slug=f"{S.SL}-2")
    with clock():
        user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert ws.slug == S.SL


def test_auth_rw_20__flushed_never_committed(db, S):
    """AUTH-RW-20 — flushed, never committed.
    Rules: _register_with_new_workspace Returns (flushed)."""
    # [claude] AUTH-RW-20
    PD(db, S)
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock():
            user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=S.EN, password=PW, workspace_name=S.WSNAME)
    # Then 1
    assert db.scalar(select(func.count()).select_from(Workspace).where(Workspace.slug == S.SL)) == 1
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert db.scalar(select(func.count()).select_from(Workspace).where(Workspace.slug == S.SL)) == 0

# --------------------------------------------------------------------------- #
# Part B
# --------------------------------------------------------------------------- #
BUG_2560 = "BUG-2560: Two refreshes with one token at once both succeed and leave two live sessions"
REUSE = "Refresh token reuse detected; all sessions for this login have been revoked"


def b_add(db, row):
    """Add one Given row and flush it."""
    db.add(row)
    db.flush()
    return row


@contextmanager
def b_failing_commit(db):
    """Convention **failing commit** (the outer `pytest.raises(RuntimeError)` is in the test): yields rb."""
    with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield rb


def b_hpw(db, *users):
    """Given `U.hashed_password = HPW; db.flush()` for each user."""
    hpw = get_password_hash(PW)
    for u in users:
        u.hashed_password = hpw
    db.flush()
    return hpw


# =========================================================================== #
# login_user
# =========================================================================== #


def test_auth_li_01__right_password_signs_in(db, S):
    """AUTH-LI-01 — the right password signs the user in.
    Rules: login_user R1, R2, Returns."""
    # [claude] AUTH-LI-01
    b_hpw(db, S.UA)
    commit_point(db)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.EA, password=PW, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert user.id == S.UA.id
    # Then 2
    assert msgs(messages) == [("success", "Welcome back, Ann Lee!")]
    # Then 3
    assert isinstance(pair, TokenPair)


def test_auth_li_02__no_workspace_new_family(db, S):
    """AUTH-LI-02 — the login session has no workspace and a new family.
    Rules: login_user R2."""
    # [claude] AUTH-LI-02
    b_hpw(db, S.UA)
    commit_point(db)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.EA, password=PW, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert "workspace_id" not in claims(pair.access_token)
    # Then 2
    assert claims(pair.access_token)["sub"] == str(S.UA.id)
    assert claims(pair.access_token)["email"] == S.EA
    assert claims(pair.access_token)["exp"] == EXP15
    # Then 3
    assert row_of(db, pair).workspace_id is None
    assert row_of(db, pair).user_agent == "Mozilla/5.0 Test"
    assert row_of(db, pair).ip_address == "203.0.113.7"
    # Then 4
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_li_03__committed_once(db, S):
    """AUTH-LI-03 — the session is committed once.
    Rules: login_user R2 (TC1)."""
    # [claude] AUTH-LI-03
    b_hpw(db, S.UA)
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        user, pair, messages = svc.login_user(db, email=S.EA, password=PW)
    # Then 1
    assert user.id == S.UA.id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert tokens(db, S.UA) == 1


def test_auth_li_04__earlier_sessions_untouched(db, S):
    """AUTH-LI-04 — earlier sessions are not touched.
    Rules: login_user R2."""
    # [claude] AUTH-LI-04
    b_hpw(db, S.UA)
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.EA, password=PW)
    # Then 1
    assert user.id == S.UA.id
    # Then 2
    assert snap(db, K) == before[K]
    # Then 3
    assert tokens(db, S.UA) == 2
    # Then 4
    assert live(db, S.UA) == 2


def test_auth_li_05__own_email_not_neighbour(db, S):
    """AUTH-LI-05 — the email of the user is used, not a neighbour's with the same password.
    Rules: login_user R1."""
    # [claude] AUTH-LI-05
    b_hpw(db, S.UA, S.UB)
    commit_point(db)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.EB, password=PW)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    assert claims(pair.access_token)["sub"] == str(S.UB.id)
    # Then 3
    assert tokens(db, S.UA) == 0


def test_auth_li_06__unknown_email_refused(db, S):
    """AUTH-LI-06 — an unknown email: the generic refusal, no write, no rollback.
    Rules: login_user R1, Errors."""
    # [claude] AUTH-LI-06
    b_hpw(db, S.UA)
    before = commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.login_user(db, email=S.EN, password=PW)
    assert str(exc.value) == BADLOGIN
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert x_count(db, X_ID) == 1
    # Then 6
    assert counts(db)["refresh_tokens"] == before["n"]["refresh_tokens"]


def test_auth_li_07__wrong_password_refused(db, S):
    """AUTH-LI-07 — a wrong password: the same refusal.
    Rules: login_user R1."""
    # [claude] AUTH-LI-07
    b_hpw(db, S.UA)
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.login_user(db, email=S.EA, password=PW2)
    assert str(exc.value) == BADLOGIN
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_li_08__empty_stored_hash_refused(db, S):
    """AUTH-LI-08 — an empty stored hash: the same refusal.
    Rules: login_user R1."""
    # [claude] AUTH-LI-08
    S.UA.hashed_password = ""
    db.flush()
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.login_user(db, email=S.EA, password=PW)
    assert str(exc.value) == BADLOGIN
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_li_09__malformed_stored_hash_refused(db, S):
    """AUTH-LI-09 — a malformed stored hash: the same refusal.
    Rules: login_user R1."""
    # [claude] AUTH-LI-09
    assert S.UA.hashed_password == "not-a-real-hash"
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.login_user(db, email=S.EA, password=PW)
    assert str(exc.value) == BADLOGIN
    # Then 2
    assert tokens(db, S.UA) == 0


@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_auth_li_10__other_capitals_find_account(db, S):
    """AUTH-LI-10 — the email in other capitals finds the account.
    Rules: login_user R1 [BUG-1860]."""
    # [claude] AUTH-LI-10
    P = make_profile(db, email=S.MIXED, name="Ann Mixed", hashed_password=get_password_hash(PW))
    commit_point(db)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.LOWER, password=PW)
    # Then 1
    assert user.id == P.id
    # Then 2
    assert tokens(db, P) == 1


def test_auth_li_11__failing_commit_rolls_back(db, S):
    """AUTH-LI-11 — a failing commit rolls back and keeps no session.
    Rules: login_user R3 (TC4)."""
    # [claude] AUTH-LI-11
    b_hpw(db, S.UA)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with b_failing_commit(db) as rb, clock():
            svc.login_user(db, email=S.EA, password=PW)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert tokens(db, S.UA) == 0


def test_auth_li_12__active_member_gets_no_workspace(db, S):
    """AUTH-LI-12 — a user with an active membership still gets a session with no workspace.
    Rules: login_user R2."""
    # [claude] AUTH-LI-12
    S.UO.hashed_password = get_password_hash(PW)
    db.flush()
    commit_point(db)
    with clock():
        user, pair, messages = svc.login_user(db, email=S.EO, password=PW)
    # Then 1
    assert user.id == S.UO.id
    # Then 2
    assert "workspace_id" not in claims(pair.access_token)
    # Then 3
    assert row_of(db, pair).workspace_id is None


def test_auth_li_13__failing_issue_rolls_back_without_commit(db, S):
    """AUTH-LI-13 — a failing issue rolls back and discards pending changes, without a commit.
    Rules: login_user R3 (TC3)."""
    # [claude] AUTH-LI-13
    b_hpw(db, S.UA)
    commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with spies(db) as (cm, rb), failing_issue():
            svc.login_user(db, email=S.EA, password=PW)
    assert str(exc.value) == "clock down"
    # Then 2
    assert x_count(db, X_ID) == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 1
    # Then 5
    assert tokens(db, S.UA) == 0


# =========================================================================== #
# switch_workspace
# =========================================================================== #


def test_auth_sw_01__active_member_gets_session(db, S):
    """AUTH-SW-01 — an active member gets a session for that workspace.
    Rules: switch_workspace R1, R3, Returns."""
    # [claude] AUTH-SW-01
    member(db, S, S.UA, "viewer")
    commit_point(db)
    with clock():
        ws, pair, messages = svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    assert msgs(messages) == [("success", "Switched to workspace: Acme Works")]
    # Then 3
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    assert claims(pair.access_token)["sub"] == str(S.UA.id)
    # Then 4
    assert row_of(db, pair).workspace_id == S.W1.id
    assert row_of(db, pair).user_agent == "Mozilla/5.0 Test"
    assert row_of(db, pair).ip_address == "203.0.113.7"
    # Then 5
    assert re.fullmatch(HEX32, row_of(db, pair).family_id) is not None


def test_auth_sw_02__committed_once(db, S):
    """AUTH-SW-02 — the switch is committed once.
    Rules: switch_workspace R3 (TC1)."""
    # [claude] AUTH-SW-02
    member(db, S, S.UA, "viewer")
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        ws, pair, messages = svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert tokens(db, S.UA) == 1


def test_auth_sw_03__no_membership_refused(db, S):
    """AUTH-SW-03 — no membership: refused, nothing written, no rollback.
    Rules: switch_workspace R1, R6, Errors."""
    # [claude] AUTH-SW-03
    commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    assert str(exc.value) == NOTMEM
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db
    # Then 4
    assert x_count(db, X_ID) == 1
    # Then 5
    assert tokens(db, S.UA) == 0


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("inactive", id="AUTH-SW-04"),
        pytest.param("suspended", id="AUTH-SW-05"),
        pytest.param("invited", id="AUTH-SW-06"),
        pytest.param("Active", id="AUTH-SW-07"),
    ],
)
def test_auth_sw_04_07__non_active_status_refused(db, S, status):
    """AUTH-SW-04 … SW-07 — an inactive, suspended, invited or "Active" member is refused.
    Rules: switch_workspace R1 (exact compare)."""
    # [claude] AUTH-SW-04, AUTH-SW-05, AUTH-SW-06, AUTH-SW-07
    member(db, S, S.UA, "viewer", status=status)
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    assert str(exc.value) == NOTMEM
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_sw_08__unknown_workspace_same_message(db, S):
    """AUTH-SW-08 — an unknown workspace gets the same message.
    Rules: switch_workspace R1 (HR-16)."""
    # [claude] AUTH-SW-08
    member(db, S, S.UA, "viewer")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=MISSING)
    assert str(exc.value) == NOTMEM
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_sw_09__other_workspaces_do_not_open_w1(db, S):
    """AUTH-SW-09 — active rows in W0 and W2 do not open W1.
    Rules: switch_workspace R1 (HR-16)."""
    # [claude] AUTH-SW-09
    member(db, S, S.UA, "viewer", ws=S.W0)
    member(db, S, S.UA, "viewer", ws=S.W2)
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    assert str(exc.value) == NOTMEM
    # Then 2
    assert tokens(db, S.UA) == 0


def test_auth_sw_10__member_row_of_another_user(db, S):
    """AUTH-SW-10 — W1's member row does not belong to another user.
    Rules: switch_workspace R1 (by workspace and user together)."""
    # [claude] AUTH-SW-10
    member(db, S, S.UA, "viewer")
    member(db, S, S.UC, "viewer")
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.switch_workspace(db, user_id=S.UB.id, workspace_id=S.W1.id)
    assert str(exc.value) == NOTMEM
    # Then 2
    assert tokens(db, S.UB) == 0


def test_auth_sw_11__finance_member_may_switch(db, S):
    """AUTH-SW-11 — the role is not checked: a finance member may switch.
    Rules: switch_workspace R4."""
    # [claude] AUTH-SW-11
    member(db, S, S.UA, "finance")
    commit_point(db)
    with clock():
        ws, pair, messages = svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    db.rollback()
    assert tokens(db, S.UA) == 1


def test_auth_sw_12__earlier_tokens_not_revoked(db, S):
    """AUTH-SW-12 — earlier refresh tokens are not revoked.
    Rules: switch_workspace R5."""
    # [claude] AUTH-SW-12
    member(db, S, S.UA, "viewer")
    K = token(db, S, S.RAW1, workspace_id=S.W2.id)
    before = commit_point(db, K)
    with clock():
        ws, pair, messages = svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    # Then 1
    assert ws.id == S.W1.id
    # Then 2
    assert snap(db, K) == before[K]
    # Then 3
    assert live(db, S.UA) == 2


def test_auth_sw_13__failing_commit_rolls_back(db, S):
    """AUTH-SW-13 — a failing commit rolls back and keeps no session.
    Rules: switch_workspace R6 (TC4)."""
    # [claude] AUTH-SW-13
    member(db, S, S.UA, "viewer")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with b_failing_commit(db) as rb, clock():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert tokens(db, S.UA) == 0


def test_auth_sw_14__failing_issue_rolls_back_without_commit(db, S):
    """AUTH-SW-14 — a failing issue rolls back and discards pending changes, without a commit.
    Rules: switch_workspace R6 (TC3)."""
    # [claude] AUTH-SW-14
    member(db, S, S.UA, "viewer")
    commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with spies(db) as (cm, rb), failing_issue():
            svc.switch_workspace(db, user_id=S.UA.id, workspace_id=S.W1.id)
    assert str(exc.value) == "clock down"
    # Then 2
    assert x_count(db, X_ID) == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 1
    # Then 5
    assert tokens(db, S.UA) == 0


# =========================================================================== #
# refresh_access_token
# =========================================================================== #


def test_auth_rf_01__live_token_new_pair_same_family(db, S):
    """AUTH-RF-01 — a live token is exchanged for a new pair in the same family.
    Rules: refresh_access_token R6, Returns."""
    # [claude] AUTH-RF-01
    token(db, S, S.RAW1, workspace_id=S.W1.id)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1, user_agent=AGENT, ip_address=IP)
    # Then 1
    assert messages == []
    # Then 2
    assert pair.refresh_token != S.RAW1
    # Then 3
    assert row_of(db, pair).family_id == S.FAM1
    assert row_of(db, pair).workspace_id == S.W1.id
    assert row_of(db, pair).user_id == S.UA.id
    # Then 4
    assert row_of(db, pair).user_agent == "Mozilla/5.0 Test"
    assert row_of(db, pair).ip_address == "203.0.113.7"
    assert row_of(db, pair).expires_at == NOW14
    # Then 5
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    assert claims(pair.access_token)["sub"] == str(S.UA.id)


def test_auth_rf_02__old_row_revoked_linked_touched(db, S):
    """AUTH-RF-02 — the old row is revoked, linked to its successor and touched.
    Rules: refresh_access_token R6."""
    # [claude] AUTH-RF-02
    K = token(db, S, S.RAW1)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert messages == []
    # Then 2
    new_id = row_of(db, pair).id
    k = reread(db, RefreshToken, K.id)
    assert k.revoked_at == NOW
    assert k.replaced_by_id == new_id
    assert k.last_used_at == NOW


def test_auth_rf_03__no_workspace_stays_none(db, S):
    """AUTH-RF-03 — a session without a workspace stays without one.
    Rules: refresh_access_token R6."""
    # [claude] AUTH-RF-03
    token(db, S, S.RAW1)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert "workspace_id" not in claims(pair.access_token)
    # Then 2
    assert row_of(db, pair).workspace_id is None


def test_auth_rf_04__rotation_committed_once(db, S):
    """AUTH-RF-04 — the rotation is committed once.
    Rules: refresh_access_token R6 (TC1)."""
    # [claude] AUTH-RF-04
    K = token(db, S, S.RAW1)
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert messages == []
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert tokens(db, S.UA) == 2
    # Then 5
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == K.id)) == NOW


def test_auth_rf_05__removed_member_still_refreshes(db, S):
    """AUTH-RF-05 — a removed member can still refresh (membership is not re-checked).
    Rules: refresh_access_token R6 (D11)."""
    # [claude] AUTH-RF-05
    member(db, S, S.UA, "viewer", status="inactive")
    token(db, S, S.RAW1, workspace_id=S.W1.id)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    # Then 2
    assert row_of(db, pair).workspace_id == S.W1.id


def test_auth_rf_06__suspended_member_still_refreshes(db, S):
    """AUTH-RF-06 — a suspended member can still refresh.
    Rules: refresh_access_token R6 (D11)."""
    # [claude] AUTH-RF-06
    member(db, S, S.UA, "viewer", status="suspended")
    K = token(db, S, S.RAW1, workspace_id=S.W1.id)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert claims(pair.access_token)["workspace_id"] == S.W1.id
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == NOW


def test_auth_rf_07__unknown_token_refused_rolled_back(db, S):
    """AUTH-RF-07 — an unknown token: refused, rolled back, pending changes discarded.
    Rules: refresh_access_token R1, R8 (TC3), Errors."""
    # [claude] AUTH-RF-07
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.refresh_access_token(db, raw_refresh_token=f"nope-{S.TAG}")
    assert str(exc.value) == "Invalid refresh token"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert snap(db, K) == before[K]
    # Then 5
    assert counts(db) == before["n"]


def test_auth_rf_08__empty_token_unknown(db, S):
    """AUTH-RF-08 — an empty token is unknown.
    Rules: refresh_access_token R1."""
    # [claude] AUTH-RF-08
    token(db, S, S.RAW1)
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.refresh_access_token(db, raw_refresh_token="")
    assert str(exc.value) == "Invalid refresh token"
    # Then 2
    assert counts(db) == before["n"]


def test_auth_rf_09__replay_revokes_family_committed(db, S):
    """AUTH-RF-09 — a replayed rotated token revokes its whole family, committed.
    Rules: refresh_access_token R2, Errors."""
    # [claude] AUTH-RF-09
    s_row = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    K = token(db, S, S.RAW1, revoked_at=EARLY, replaced_by_id=s_row.id)
    T = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW3), family_id=S.FAM2, workspace_id=None, expires_at=LATER))
    V = b_add(db, RefreshToken(user_id=S.UB.id, token_hash=hash_refresh_token(S.RAW4), family_id=S.FAM2, workspace_id=None, expires_at=LATER))
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == REUSE
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == s_row.id)) == NOW
    # Then 4
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == K.id)) == EARLY
    # Then 5
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == T.id)) is None
    # Then 6
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == V.id)) is None
    # Then 7
    assert counts(db)["refresh_tokens"] == before["n"]["refresh_tokens"]


def test_auth_rf_10__reuse_checked_before_expiry(db, S):
    """AUTH-RF-10 — reuse is checked before expiry.
    Rules: refresh_access_token R3."""
    # [claude] AUTH-RF-10
    s_row = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    token(db, S, S.RAW1, expires_at=PAST, revoked_at=EARLY, replaced_by_id=s_row.id)
    commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == REUSE
    # Then 2
    db.rollback()
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == s_row.id)) == NOW


def test_auth_rf_11__revoked_without_successor_refused(db, S):
    """AUTH-RF-11 — a revoked token without successor is refused and nothing changes.
    Rules: refresh_access_token R4, R8, Errors."""
    # [claude] AUTH-RF-11
    s_row = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    K = token(db, S, S.RAW1, revoked_at=EARLY)
    before = commit_point(db, K, s_row)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == "Refresh token has been revoked"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert snap(db, K) == before[K]
    # Then 4
    assert snap(db, s_row) == before[s_row]
    # Then 5
    assert counts(db) == before["n"]


def test_auth_rf_12__expiring_exactly_now_is_expired(db, S):
    """AUTH-RF-12 — a token expiring exactly now is expired.
    Rules: refresh_access_token R4, Errors."""
    # [claude] AUTH-RF-12
    K = token(db, S, S.RAW1, expires_at=NOW)
    before = commit_point(db, K)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == "Refresh token has expired"
    # Then 2
    assert snap(db, K) == before[K]
    # Then 3
    assert counts(db) == before["n"]


def test_auth_rf_13__one_microsecond_left_still_refreshes(db, S):
    """AUTH-RF-13 — a token one microsecond from expiry still refreshes.
    Rules: refresh_access_token R4."""
    # [claude] AUTH-RF-13
    K = token(db, S, S.RAW1, expires_at=NOW + US)
    commit_point(db)
    with clock():
        pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert messages == []
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == NOW


def test_auth_rf_14__same_token_twice_is_reuse(db, S):
    """AUTH-RF-14 — the same token presented twice in turn: the second is reuse.
    Rules: refresh_access_token R6, R7 (the sequential replay), R2."""
    # [claude] AUTH-RF-14
    token(db, S, S.RAW1)
    commit_point(db)
    with clock():
        first, _ = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == REUSE
    # Then 2
    db.rollback()
    assert row_of(db, first).revoked_at == NOW
    # Then 3
    assert live(db, S.UA) == 0
    # Then 4
    assert tokens(db, S.UA) == 2


@pytest.mark.xfail(strict=True, reason=BUG_2560)
def test_auth_rf_15__presented_row_read_with_lock(db, S):
    """AUTH-RF-15 — the presented row is read with a row lock.
    Rules: refresh_access_token R7 [BUG-2560]."""
    # [claude] AUTH-RF-15
    token(db, S, S.RAW1)
    commit_point(db)
    rec = Recorder(db)
    try:
        with clock():
            pair, messages = svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    finally:
        rec.stop()
    # Then 1
    first_insert = next(i for i, s in enumerate(rec.stmts) if s.startswith("INSERT INTO refresh_tokens"))
    lookups = [s for s in rec.stmts[:first_insert] if s.lstrip().upper().startswith("SELECT") and "FROM refresh_tokens" in s and "token_hash" in s]
    assert len(lookups) == 1
    sql = lookups[0]
    # Then 2
    assert "FOR UPDATE" in sql.upper()


def test_auth_rf_16__failing_commit_keeps_old_token_live(db, S):
    """AUTH-RF-16 — a failing commit leaves the old token live and no successor.
    Rules: refresh_access_token R8 (TC4)."""
    # [claude] AUTH-RF-16
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with b_failing_commit(db) as rb, clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, K) == before[K]
    # Then 4
    assert tokens(db, S.UA) == 1


def test_auth_rf_17__reuse_commit_commits_pending_changes(db, S):
    """AUTH-RF-17 — the reuse commit also commits other pending changes.
    Rules: refresh_access_token R2a."""
    # [claude] AUTH-RF-17
    s_row = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    token(db, S, S.RAW1, revoked_at=EARLY, replaced_by_id=s_row.id)
    commit_point(db)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.refresh_access_token(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == REUSE
    # Then 2
    db.rollback()
    assert x_count(db, X_ID) == 1
    # Then 3
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == s_row.id)) == NOW


# =========================================================================== #
# logout_session
# =========================================================================== #


def test_auth_lo_01__live_token_revoked_alone(db, S):
    """AUTH-LO-01 — a live token is revoked alone, with no successor.
    Rules: logout_session R4, Returns."""
    # [claude] AUTH-LO-01
    K = token(db, S, S.RAW1)
    s_row = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    before = commit_point(db, s_row)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert msgs(messages) == [("success", "Logged out.")]
    # Then 2
    k = reread(db, RefreshToken, K.id)
    assert k.revoked_at == NOW
    assert k.replaced_by_id is None
    assert k.last_used_at is None
    # Then 3
    assert snap(db, s_row) == before[s_row]


def test_auth_lo_02__logout_committed(db, S):
    """AUTH-LO-02 — the logout is committed.
    Rules: logout_session R6 (TC1)."""
    # [claude] AUTH-LO-02
    K = token(db, S, S.RAW1)
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        messages = svc.logout_session(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert msgs(messages) == [("success", "Logged out.")]
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == K.id)) == NOW


def test_auth_lo_03__unknown_token_no_error(db, S):
    """AUTH-LO-03 — an unknown token is no error and changes nothing.
    Rules: logout_session R4."""
    # [claude] AUTH-LO-03
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=f"nope-{S.TAG}")
    # Then 1
    assert msgs(messages) == [("success", "Logged out.")]
    # Then 2
    assert snap(db, K) == before[K]
    # Then 3
    assert counts(db) == before["n"]


def test_auth_lo_04__already_revoked_keeps_first_stamp(db, S):
    """AUTH-LO-04 — an already revoked token keeps its first stamp.
    Rules: logout_session R4."""
    # [claude] AUTH-LO-04
    K = token(db, S, S.RAW1, revoked_at=EARLY)
    commit_point(db)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert msgs(messages) == [("success", "Logged out.")]
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == EARLY


def test_auth_lo_05__expired_unrevoked_is_revoked(db, S):
    """AUTH-LO-05 — an expired, unrevoked token is revoked.
    Rules: logout_session R4."""
    # [claude] AUTH-LO-05
    K = token(db, S, S.RAW1, expires_at=PAST)
    commit_point(db)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=S.RAW1)
    # Then 1
    assert msgs(messages) == [("success", "Logged out.")]
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == NOW


def test_auth_lo_06__no_token_info_still_committed(db, S):
    """AUTH-LO-06 — no token: info message, and the session is still committed.
    Rules: logout_session R5, R6."""
    # [claude] AUTH-LO-06
    K = token(db, S, S.RAW1)
    commit_point(db)
    X, X_ID = extra_row(db, S)
    with spies(db) as (cm, rb), clock():
        messages = svc.logout_session(db, raw_refresh_token=None)
    # Then 1
    assert msgs(messages) == [("info", "No refresh token provided; nothing to revoke.")]
    # Then 2
    assert cm.call_count == 1
    # Then 3
    db.rollback()
    assert x_count(db, X_ID) == 1
    # Then 4
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.id == K.id)) is None


def test_auth_lo_07__empty_token_is_no_token(db, S):
    """AUTH-LO-07 — an empty token is "no token".
    Rules: logout_session R5."""
    # [claude] AUTH-LO-07
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token="")
    # Then 1
    assert msgs(messages) == [("info", "No refresh token provided; nothing to revoke.")]
    # Then 2
    assert snap(db, K) == before[K]


def test_auth_lo_08__all_devices_revokes_every_live_row(db, S):
    """AUTH-LO-08 — all devices: every unrevoked row of the user, in every family and workspace.
    Rules: logout_session R3."""
    # [claude] AUTH-LO-08
    T0 = b_add(db, RefreshToken(user_id=S.U0.id, token_hash=hash_refresh_token(S.RAW5), family_id=S.FAM2, workspace_id=None, expires_at=LATER))
    K = token(db, S, S.RAW1, workspace_id=S.W1.id)
    K2 = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW2), family_id=S.FAM2, workspace_id=S.W2.id, expires_at=LATER))
    K3 = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW3), family_id=S.FAM2, workspace_id=None, expires_at=PAST))
    K4 = b_add(db, RefreshToken(user_id=S.UA.id, token_hash=hash_refresh_token(S.RAW4), family_id=S.FAM1, workspace_id=None, expires_at=LATER, revoked_at=EARLY))
    TB = b_add(db, RefreshToken(user_id=S.UB.id, token_hash=hash_refresh_token(S.RAW6), family_id=S.FAM1, workspace_id=None, expires_at=LATER))
    before = commit_point(db, T0, TB)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=None, user_id=S.UA.id, all_devices=True)
    # Then 1
    assert msgs(messages) == [("success", "Revoked 3 active session(s).")]
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == NOW
    assert reread(db, RefreshToken, K2.id).revoked_at == NOW
    assert reread(db, RefreshToken, K3.id).revoked_at == NOW
    # Then 3
    assert reread(db, RefreshToken, K4.id).revoked_at == EARLY
    # Then 4
    assert snap(db, T0) == before[T0]
    # Then 5
    assert snap(db, TB) == before[TB]


def test_auth_lo_09__all_devices_ignores_presented_token(db, S):
    """AUTH-LO-09 — all devices ignores the token presented.
    Rules: logout_session R1."""
    # [claude] AUTH-LO-09
    K = token(db, S, S.RAW1)
    TB = b_add(db, RefreshToken(user_id=S.UB.id, token_hash=hash_refresh_token(S.RAW6), family_id=S.FAM2, workspace_id=None, expires_at=LATER))
    before = commit_point(db, TB)
    with clock():
        messages = svc.logout_session(db, raw_refresh_token=S.RAW6, user_id=S.UA.id, all_devices=True)
    # Then 1
    assert msgs(messages) == [("success", "Revoked 1 active session(s).")]
    # Then 2
    assert reread(db, RefreshToken, K.id).revoked_at == NOW
    # Then 3
    assert snap(db, TB) == before[TB]


def test_auth_lo_10__all_devices_none_left_says_zero(db, S):
    """AUTH-LO-10 — all devices with no session left says 0.
    Rules: logout_session R3."""
    # [claude] AUTH-LO-10
    commit_point(db)
    with spies(db) as (cm, rb), clock():
        messages = svc.logout_session(db, raw_refresh_token=None, user_id=S.UA.id, all_devices=True)
    # Then 1
    assert msgs(messages) == [("success", "Revoked 0 active session(s).")]
    # Then 2
    assert cm.call_count == 1


def test_auth_lo_11__all_devices_without_user_refused(db, S):
    """AUTH-LO-11 — all devices without a user: refused, rolled back, nothing changed.
    Rules: logout_session R2, R6, Errors."""
    # [claude] AUTH-LO-11
    K = token(db, S, S.RAW1)
    before = commit_point(db, K)
    X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (cm, rb), clock():
            svc.logout_session(db, raw_refresh_token=S.RAW1, user_id=None, all_devices=True)
    assert str(exc.value) == "Cannot logout all devices without an authenticated user"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert snap(db, K) == before[K]


def test_auth_lo_12__failing_commit_leaves_token_live(db, S):
    """AUTH-LO-12 — a failing commit leaves the token live.
    Rules: logout_session R6 (TC4)."""
    # [claude] AUTH-LO-12
    K = token(db, S, S.RAW1)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with b_failing_commit(db) as rb, clock():
            svc.logout_session(db, raw_refresh_token=S.RAW1)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, RefreshToken, K.id).revoked_at is None


# =========================================================================== #
# request_password_reset
# =========================================================================== #


def test_auth_fp_01__unknown_email_generic_message(db, S):
    """AUTH-FP-01 — an unknown email gets a token and the generic message.
    Rules: request_password_reset R2."""
    # [claude] AUTH-FP-01
    with clock():
        token_, expires_at, messages = svc.request_password_reset(db, email=S.EN)
    # Then 1
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token_) is not None
    # Then 2
    assert expires_at == NOW + timedelta(hours=1)
    # Then 3
    assert msgs(messages) == [("info", "If an account with that email exists, a password reset link has been sent.")]


def test_auth_fp_02__account_gets_placeholder_messages(db, S):
    """AUTH-FP-02 — an account gets a token and the placeholder messages, with the email as passed.
    Rules: request_password_reset R1, R3."""
    # [claude] AUTH-FP-02
    make_profile(db, email=S.MIXED, name="Ann Mixed")
    with clock():
        token_, expires_at, messages = svc.request_password_reset(db, email=S.MIXED)
    # Then 1
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token_) is not None
    # Then 2
    assert expires_at == NOW + timedelta(hours=1)
    # Then 3
    assert msgs(messages) == [
        ("success", f"Password reset token generated for {S.MIXED}. Token expires in 1 hour."),
        ("info", "NOTE: Token storage not yet implemented. Store this token securely and validate on reset."),
    ]


@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_auth_fp_03__other_capitals_find_account(db, S):
    """AUTH-FP-03 — the email in other capitals finds the account.
    Rules: request_password_reset R1 [BUG-1860]."""
    # [claude] AUTH-FP-03
    make_profile(db, email=S.MIXED, name="Ann Mixed")
    with clock():
        token_, expires_at, messages = svc.request_password_reset(db, email=S.LOWER)
    # Then 1
    assert expires_at == NOW + timedelta(hours=1)
    # Then 2
    assert msgs(messages)[0] == ("success", f"Password reset token generated for {S.LOWER}. Token expires in 1 hour.")


def test_auth_fp_04__nothing_stored_committed_rolled_back(db, S):
    """AUTH-FP-04 — nothing is stored, committed or rolled back.
    Rules: request_password_reset R4 (TC6)."""
    # [claude] AUTH-FP-04
    before = commit_point(db, S.UA)
    X, X_ID = extra_row(db, S)
    with spies(db) as (cm, rb), clock():
        token_, expires_at, messages = svc.request_password_reset(db, email=S.EA)
    # Then 1
    assert len(token_) == 43
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert snap(db, S.UA) == before[S.UA]


# =========================================================================== #
# reset_password
# =========================================================================== #


def test_auth_rp_01__refused_as_not_implemented(db, S):
    """AUTH-RP-01 — any input is refused as not implemented, nothing changes.
    Rules: reset_password R1, Errors."""
    # [claude] AUTH-RP-01
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(NotImplementedError) as exc:
        with spies(db) as (cm, rb):
            svc.reset_password(db, reset_token="anything", new_password=PW2)
    assert str(exc.value) == "Password reset requires a password_reset_tokens table. Please implement password_reset model, DAO, and schema first."
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert snap(db, S.UA) == before[S.UA]

# --------------------------------------------------------------------------- #
# Part C
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Fork C local constants and helpers
# --------------------------------------------------------------------------- #

ADMIN_NOT_MEMBER = "Admin is not a member of this workspace"
ONLY_OWNERS = "Only workspace owners can reset user passwords"
TARGET_NOT_MEMBER = "Target user is not a member of this workspace"

BUG_2569 = "BUG-2569: An owner's reset of a member's password leaves no audit row"
BUG_2561 = "BUG-2561: Invitation preview accepts an invitation at the exact instant it expires"
BUG_1406 = "BUG-1406: A person's name is stored untrimmed and may be blank"
BUG_1866 = "BUG-1866: Stamp picture address taken from the client: colleagues' browsers load any web address"
BUG_1864 = "BUG-1864: HIGH — a stamp can claim any Cloudinary file as its picture"
BUG_2568 = "BUG-2568: Replacing an image stamp with a drawn one leaves the picture in Cloudinary"
BUG_1865 = "BUG-1865: HIGH — removing your stamp deletes any image file the company stores"
BUG_2562 = "BUG-2562: Removing or replacing a stamp deletes the old picture before the change is saved"


def c_rt(db, user, raw, family, ws, expires_at, **over):
    """Given `RefreshToken(user_id=…, token_hash=hash_refresh_token(raw), family_id=…, workspace_id=…, expires_at=…)`; flushed."""
    row = RefreshToken(user_id=user.id, token_hash=hash_refresh_token(raw), family_id=family,
                       workspace_id=ws, expires_at=expires_at, **over)
    db.add(row)
    db.flush()
    return row


def c_committed_ua(db, S):
    """`committed:` line on UA: `db.rollback()` once, then a fresh read."""
    db.rollback()
    return reread(db, Profile, S.UA.id)


def c_stamp(db, S, stamp):
    """Given "UA stamp S" = `UA.saved_stamp = S; db.flush()`."""
    S.UA.saved_stamp = stamp
    db.flush()


# =========================================================================== #
# reset_password_by_admin
# =========================================================================== #


def test_auth_ar_01__owner_sets_members_new_password(db, S):
    """AUTH-AR-01 — the owner sets a member's new password.
    Rules: reset_password_by_admin R6, Returns."""
    # [claude] AUTH-AR-01
    HPW = get_password_hash(PW)
    member(db, S, S.UB, "ground-team")
    S.UB.hashed_password = HPW
    db.flush()
    commit_point(db)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    row = reread(db, Profile, S.UB.id)
    assert verify_password(PW2, row.hashed_password) is True
    # Then 3
    assert verify_password(PW, row.hashed_password) is False


def test_auth_ar_02__every_unrevoked_session_revoked_and_counted(db, S):
    """AUTH-AR-02 — every unrevoked session of the target is revoked, and the messages say how many.
    Rules: reset_password_by_admin R8, R10."""
    # [claude] AUTH-AR-02
    member(db, S, S.UB, "ground-team")
    B1 = c_rt(db, S.UB, S.RAW1, S.FAM1, S.W1.id, LATER)
    B2 = c_rt(db, S.UB, S.RAW2, S.FAM2, S.W2.id, LATER)
    B3 = c_rt(db, S.UB, S.RAW3, S.FAM2, None, PAST)
    B4 = c_rt(db, S.UB, S.RAW4, S.FAM1, None, LATER, revoked_at=EARLY)
    A1 = c_rt(db, S.UA, S.RAW5, S.FAM2, S.W1.id, LATER)
    O1 = c_rt(db, S.UO, S.RAW6, S.FAM1, S.W1.id, LATER)
    before = commit_point(db, A1, O1)
    with clock():
        _user, messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert msgs(messages) == [("success", f"Password reset successfully for user: {S.EB}"), ("info", "Revoked 3 active session(s); user must log in again."), ("info", "User should be notified of password change via email.")]
    # Then 2
    for b in (B1, B2, B3):
        assert reread(db, RefreshToken, b.id).revoked_at == NOW
    # Then 3
    assert reread(db, RefreshToken, B4.id).revoked_at == EARLY
    # Then 4
    assert snap(db, A1) == before[A1]
    # Then 5
    assert snap(db, O1) == before[O1]


def test_auth_ar_03__no_session_no_count_line(db, S):
    """AUTH-AR-03 — with no session to revoke, the count line is left out.
    Rules: reset_password_by_admin R10."""
    # [claude] AUTH-AR-03
    member(db, S, S.UB, "ground-team")
    commit_point(db)
    with clock():
        _user, messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert msgs(messages) == [("success", f"Password reset successfully for user: {S.EB}"), ("info", "User should be notified of password change via email.")]


def test_auth_ar_04__reset_committed_once(db, S):
    """AUTH-AR-04 — the reset is committed once.
    Rules: reset_password_by_admin R10 (TC1)."""
    # [claude] AUTH-AR-04
    member(db, S, S.UB, "ground-team")
    commit_point(db)
    with spies(db) as (cm, rb):
        with clock():
            user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert verify_password(PW2, profile(db, S.EB).hashed_password) is True


def test_auth_ar_05__caller_without_membership_refused(db, S):
    """AUTH-AR-05 — a caller with no membership: refused, rolled back, nothing changed.
    Rules: reset_password_by_admin R1, R5, Errors."""
    # [claude] AUTH-AR-05
    member(db, S, S.UB, "ground-team")
    B1 = c_rt(db, S.UB, S.RAW1, S.FAM1, S.W1.id, LATER)
    before = commit_point(db, S.UB, B1)
    _X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (_cm, rb):
            with clock():
                svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert snap(db, S.UB) == before[S.UB]
    # Then 5
    assert snap(db, B1) == before[B1]


def test_auth_ar_06__inactive_owner_row_is_not_membership(db, S):
    """AUTH-AR-06 — an inactive owner row is not a membership.
    Rules: reset_password_by_admin R1."""
    # [claude] AUTH-AR-06
    member(db, S, S.UA, "owner", status="inactive")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_07__suspended_owner_row_is_not_membership(db, S):
    """AUTH-AR-07 — a suspended owner row is not a membership.
    Rules: reset_password_by_admin R1."""
    # [claude] AUTH-AR-07
    member(db, S, S.UA, "owner", status="suspended")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_08__owner_of_w0_has_no_grant_in_w1(db, S):
    """AUTH-AR-08 — the owner of W0 (lower id) has no grant in W1.
    Rules: reset_password_by_admin R1 (HR-16)."""
    # [claude] AUTH-AR-08
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.U0.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_09__owner_of_w2_has_no_grant_in_w1(db, S):
    """AUTH-AR-09 — the owner of W2 (higher id) has no grant in W1.
    Rules: reset_password_by_admin R1 (HR-16)."""
    # [claude] AUTH-AR-09
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.U2.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_10__manager_may_not_reset(db, S):
    """AUTH-AR-10 — a manager may not reset passwords.
    Rules: reset_password_by_admin R2, Errors."""
    # [claude] AUTH-AR-10
    member(db, S, S.UA, "manager")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    _X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (_cm, rb):
            with clock():
                svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_11__role_owner_in_capitals_is_not_owner(db, S):
    """AUTH-AR-11 — role "Owner" in capitals is not owner.
    Rules: reset_password_by_admin R2 (exact compare)."""
    # [claude] AUTH-AR-11
    member(db, S, S.UA, "Owner")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_12__ground_team_manager_may_not_reset(db, S):
    """AUTH-AR-12 — a ground-team-manager may not reset passwords.
    Rules: reset_password_by_admin R2."""
    # [claude] AUTH-AR-12
    member(db, S, S.UA, "ground-team-manager")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_13__finance_member_may_not_reset(db, S):
    """AUTH-AR-13 — a finance member may not reset passwords.
    Rules: reset_password_by_admin R2."""
    # [claude] AUTH-AR-13
    member(db, S, S.UA, "finance")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_14__owner_user_id_does_not_count(db, S):
    """AUTH-AR-14 — being named owner_user_id does not count, only the member role.
    Rules: reset_password_by_admin R2."""
    # [claude] AUTH-AR-14
    S.W1.owner_user_id = S.UA.id
    db.flush()
    member(db, S, S.UA, "manager")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_15__platform_admin_manager_gets_no_exception(db, S):
    """AUTH-AR-15 — a platform admin with a manager role gets no exception.
    Rules: reset_password_by_admin R2."""
    # [claude] AUTH-AR-15
    S.UA.is_platform_admin = True
    db.flush()
    member(db, S, S.UA, "manager")
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_16__target_without_membership_refused(db, S):
    """AUTH-AR-16 — a target with no membership: refused, nothing changed.
    Rules: reset_password_by_admin R3, R5, Errors."""
    # [claude] AUTH-AR-16
    member(db, S, S.UB, "ground-team")
    before = commit_point(db, S.UC)
    _X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (_cm, rb):
            with clock():
                svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UC.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_count(db, X_ID) == 0
    # Then 4
    assert snap(db, S.UC) == before[S.UC]


def test_auth_ar_17__suspended_target_refused(db, S):
    """AUTH-AR-17 — a suspended target is refused.
    Rules: reset_password_by_admin R3."""
    # [claude] AUTH-AR-17
    member(db, S, S.UB, "ground-team", status="suspended")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_18__inactive_target_refused(db, S):
    """AUTH-AR-18 — a removed (inactive) target is refused.
    Rules: reset_password_by_admin R3."""
    # [claude] AUTH-AR-18
    member(db, S, S.UB, "ground-team", status="inactive")
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_19__target_member_of_w0_only_refused(db, S):
    """AUTH-AR-19 — a target who is a member of W0 only is refused.
    Rules: reset_password_by_admin R3 (HR-16)."""
    # [claude] AUTH-AR-19
    member(db, S, S.UB, "ground-team", ws=S.W0)
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_20__target_member_of_w2_only_refused(db, S):
    """AUTH-AR-20 — a target who is a member of W2 only is refused.
    Rules: reset_password_by_admin R3 (HR-16)."""
    # [claude] AUTH-AR-20
    member(db, S, S.UB, "ground-team", ws=S.W2)
    before = commit_point(db, S.UB)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert snap(db, S.UB) == before[S.UB]


def test_auth_ar_21__unknown_target_refused_as_not_member(db, S):
    """AUTH-AR-21 — an unknown target id is refused as not a member.
    Rules: reset_password_by_admin R3."""
    # [claude] AUTH-AR-21
    member(db, S, S.UB, "ground-team")
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=MISSING, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == TARGET_NOT_MEMBER
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ar_22__caller_checked_before_target(db, S):
    """AUTH-AR-22 — the caller is checked before the target.
    Rules: reset_password_by_admin R5 (R1 before R3)."""
    # [claude] AUTH-AR-22
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UC.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ADMIN_NOT_MEMBER
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ar_23__role_checked_before_target(db, S):
    """AUTH-AR-23 — the role is checked before the target.
    Rules: reset_password_by_admin R5 (R2 before R3)."""
    # [claude] AUTH-AR-23
    member(db, S, S.UA, "manager")
    before = commit_point(db)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with clock():
            svc.reset_password_by_admin(db, admin_user_id=S.UA.id, target_user_id=S.UC.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == ONLY_OWNERS
    # Then 2
    assert counts(db) == before["n"]


def test_auth_ar_24__password_over_72_bytes_refused(db, S):
    """AUTH-AR-24 — a password over 72 bytes is refused and no session is revoked.
    Rules: reset_password_by_admin R6, Errors."""
    # [claude] AUTH-AR-24
    HPW = get_password_hash(PW)
    member(db, S, S.UB, "ground-team")
    S.UB.hashed_password = HPW
    db.flush()
    B1 = c_rt(db, S.UB, S.RAW1, S.FAM1, S.W1.id, LATER)
    before = commit_point(db, S.UB, B1)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (_cm, rb):
            with clock():
                svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password="a" * 73, workspace_id=S.W1.id)
    assert str(exc.value) == "Password exceeds bcrypt's 72-byte limit"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert snap(db, S.UB) == before[S.UB]
    # Then 4
    assert snap(db, B1) == before[B1]


def test_auth_ar_25__password_of_exactly_72_bytes_accepted(db, S):
    """AUTH-AR-25 — a password of exactly 72 bytes is accepted.
    Rules: reset_password_by_admin R6."""
    # [claude] AUTH-AR-25
    member(db, S, S.UB, "ground-team")
    commit_point(db)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password="a" * 72, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    row = reread(db, Profile, S.UB.id)
    assert verify_password("a" * 72, row.hashed_password) is True


@pytest.mark.xfail(strict=True, reason=BUG_2569)
def test_auth_ar_26__reset_leaves_one_audit_row_without_password(db, S):
    """AUTH-AR-26 — the reset leaves one audit row with no password in it.
    Rules: reset_password_by_admin R9 [BUG-2569]."""
    # [claude] AUTH-AR-26
    member(db, S, S.UB, "ground-team")
    c_rt(db, S.UB, S.RAW1, S.FAM1, S.W1.id, LATER)
    commit_point(db)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    rows = audit(db, S.W1, "member_password_reset")
    assert len(rows) == 1
    # Then 3
    row = rows[0]
    assert row.user_id == S.UO.id
    assert row.metadata_json == {"target_user_id": S.UB.id, "sessions_revoked": 1}
    # Then 4
    assert PW2 not in str(row.metadata_json)
    # Then 5
    assert profile(db, S.EB).hashed_password not in str(row.metadata_json)


def test_auth_ar_27__failing_commit_keeps_old_password_and_sessions(db, S):
    """AUTH-AR-27 — a failing commit keeps the old password and the sessions.
    Rules: reset_password_by_admin R10 (TC4)."""
    # [claude] AUTH-AR-27
    HPW = get_password_hash(PW)
    member(db, S, S.UB, "ground-team")
    S.UB.hashed_password = HPW
    db.flush()
    B1 = c_rt(db, S.UB, S.RAW1, S.FAM1, S.W1.id, LATER)
    before = commit_point(db, B1)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:
            with clock():
                svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, Profile, S.UB.id)
    assert verify_password(PW, row.hashed_password) is True
    # Then 4
    assert snap(db, B1) == before[B1]


# =========================================================================== #
# reset_password_by_admin — pending OQ-34 (R7, today's behaviour)
# =========================================================================== #


def test_auth_p34_01__owner_resets_own_password(db, S):
    """AUTH-P34-01 — an owner may reset their own password without the old one (pending OQ-34).
    Rules: reset_password_by_admin R7 (pending OQ-34)."""
    # [claude] AUTH-P34-01
    HPW = get_password_hash(PW)
    S.UO.hashed_password = HPW
    db.flush()
    commit_point(db)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UO.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UO.id
    # Then 2
    db.rollback()
    assert verify_password(PW2, profile(db, S.EO).hashed_password) is True


def test_auth_p34_02__owner_resets_another_owner_role_member(db, S):
    """AUTH-P34-02 — an owner may reset another owner-role member (pending OQ-34).
    Rules: reset_password_by_admin R7 (pending OQ-34)."""
    # [claude] AUTH-P34-02
    member(db, S, S.UA, "owner")
    commit_point(db)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UA.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UA.id
    # Then 2
    db.rollback()
    assert verify_password(PW2, profile(db, S.EA).hashed_password) is True


def test_auth_p34_03__platform_admin_owning_other_workspace_reset_globally(db, S):
    """AUTH-P34-03 — a platform admin who owns another workspace can be reset; the password is global (pending OQ-34).
    Rules: reset_password_by_admin R7 (pending OQ-34)."""
    # [claude] AUTH-P34-03
    HPW = get_password_hash(PW)
    S.UB.is_platform_admin = True
    S.UB.hashed_password = HPW
    db.flush()
    member(db, S, S.UB, "ground-team")
    W3 = make_workspace(db, subscription_plan_id=S.PL2.id, owner_user_id=S.UB.id)
    MB3 = member(db, S, S.UB, "owner", ws=W3)
    before = commit_point(db, MB3)
    with clock():
        user, _messages = svc.reset_password_by_admin(db, admin_user_id=S.UO.id, target_user_id=S.UB.id, new_password=PW2, workspace_id=S.W1.id)
    # Then 1
    assert user.id == S.UB.id
    # Then 2
    db.rollback()
    assert verify_password(PW2, profile(db, S.EB).hashed_password) is True
    # Then 3
    assert profile(db, S.EB).is_platform_admin is True
    # Then 4
    assert snap(db, MB3) == before[MB3]


# =========================================================================== #
# validate_invitation_token
# =========================================================================== #


def test_auth_vi_01__valid_token_shows_invitation(db, S):
    """AUTH-VI-01 — a valid token shows exactly what the invitation offers.
    Rules: validate_invitation_token R5, Returns."""
    # [claude] AUTH-VI-01
    I = invitation(db, S, "I", f"inv.{S.TAG}@acme.com", role="viewer", position="Supervisor")
    with clock():
        details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert details == {"invitation_id": I.id, "email": f"inv.{S.TAG}@acme.com", "role": "viewer", "position": "Supervisor", "workspace_id": S.W1.id, "workspace_name": "Acme Works", "expires_at": "2099-01-01T00:00:00"}
    # Then 2
    assert msgs(messages) == [("success", "Valid invitation to join 'Acme Works' as viewer")]


def test_auth_vi_02__no_position_shows_none(db, S):
    """AUTH-VI-02 — no position shows None.
    Rules: validate_invitation_token R5."""
    # [claude] AUTH-VI-02
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    with clock():
        details, _messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert details["position"] is None
    # Then 2
    assert details["role"] == "member"


def test_auth_vi_03__token_decides_the_workspace(db, S):
    """AUTH-VI-03 — the token decides the workspace: W2's invitation shows W2.
    Rules: validate_invitation_token R1, R5 (any workspace)."""
    # [claude] AUTH-VI-03
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    J = invitation(db, S, "J", f"inv.{S.TAG}@acme.com", workspace_id=S.W2.id, invited_by_user_id=S.U2.id)
    with clock():
        details, _messages = svc.validate_invitation_token(db, invitation_token=f"inv-J-{S.TAG}")
    # Then 1
    assert details["invitation_id"] == J.id
    # Then 2
    assert details["workspace_id"] == S.W2.id
    assert details["workspace_name"] == "Tom Works"


def test_auth_vi_04__unknown_token_refused(db, S):
    """AUTH-VI-04 — an unknown token is refused.
    Rules: validate_invitation_token R1, Errors."""
    # [claude] AUTH-VI-04
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-Z-{S.TAG}")
    assert str(exc.value) == "Invalid invitation token"


def test_auth_vi_05__token_in_capitals_is_unknown(db, S):
    """AUTH-VI-05 — the token in capitals is unknown.
    Rules: validate_invitation_token R1 (exact)."""
    # [claude] AUTH-VI-05
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"INV-I-{S.TAG.upper()}")
    assert str(exc.value) == "Invalid invitation token"


def test_auth_vi_06__part_of_token_is_unknown(db, S):
    """AUTH-VI-06 — a part of the token is unknown.
    Rules: validate_invitation_token R1 (exact)."""
    # [claude] AUTH-VI-06
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}"[:-1])
    assert str(exc.value) == "Invalid invitation token"


@pytest.mark.xfail(strict=True, reason=BUG_2561)
def test_auth_vi_07__expiring_exactly_now_is_expired(db, S):
    """AUTH-VI-07 — an invitation expiring exactly now is expired.
    Rules: validate_invitation_token R2 [BUG-2561]."""
    # [claude] AUTH-VI-07
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", expires_at=NOW)
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == EXPIRED_INV


def test_auth_vi_08__one_microsecond_past_expiry_is_expired(db, S):
    """AUTH-VI-08 — one microsecond past expiry is expired.
    Rules: validate_invitation_token R2, Errors."""
    # [claude] AUTH-VI-08
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", expires_at=NOW - US)
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == EXPIRED_INV


def test_auth_vi_09__one_microsecond_before_expiry_is_valid(db, S):
    """AUTH-VI-09 — one microsecond before expiry is valid.
    Rules: validate_invitation_token R2, R5."""
    # [claude] AUTH-VI-09
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", expires_at=NOW + US)
    with clock():
        details, _messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert details["expires_at"] == "2026-03-05T12:00:00.000001"


def test_auth_vi_10__expiry_checked_before_status(db, S):
    """AUTH-VI-10 — expiry is checked before status.
    Rules: validate_invitation_token R3."""
    # [claude] AUTH-VI-10
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", status="accepted", expires_at=PAST)
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == EXPIRED_INV


def test_auth_vi_11__accepted_invitation_says_so(db, S):
    """AUTH-VI-11 — an accepted invitation says so.
    Rules: validate_invitation_token R4, Errors."""
    # [claude] AUTH-VI-11
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", status="accepted")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Invitation has already been accepted"


def test_auth_vi_12__cancelled_invitation_says_so(db, S):
    """AUTH-VI-12 — a cancelled invitation says so.
    Rules: validate_invitation_token R4."""
    # [claude] AUTH-VI-12
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", status="cancelled")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Invitation has already been cancelled"


def test_auth_vi_13__status_pending_in_capitals_is_not_pending(db, S):
    """AUTH-VI-13 — status "Pending" in capitals is not pending.
    Rules: validate_invitation_token R4 (exact)."""
    # [claude] AUTH-VI-13
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com", status="Pending")
    # Then 1
    with pytest.raises(ValueError) as exc, clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    assert str(exc.value) == "Invitation has already been Pending"


def test_auth_vi_14__preview_writes_commits_and_rolls_back_nothing(db, S):
    """AUTH-VI-14 — the preview writes, commits and rolls back nothing.
    Rules: validate_invitation_token R6 (TC6)."""
    # [claude] AUTH-VI-14
    I = invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    before = commit_point(db, I)
    X, _X_ID = extra_row(db, S)
    with spies(db) as (cm, rb):
        with clock():
            details, _messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{S.TAG}")
    # Then 1
    assert details["invitation_id"] == I.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert snap(db, I) == before[I]


def test_auth_vi_15__refusal_does_not_roll_back(db, S):
    """AUTH-VI-15 — a refusal does not roll back either.
    Rules: validate_invitation_token R6 (TC6)."""
    # [claude] AUTH-VI-15
    invitation(db, S, "I", f"inv.{S.TAG}@acme.com")
    commit_point(db)
    X, _X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc, spies(db) as (_cm, rb), clock():
        svc.validate_invitation_token(db, invitation_token=f"inv-Z-{S.TAG}")
    assert str(exc.value) == "Invalid invitation token"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


# =========================================================================== #
# update_current_user (every card runs with dr)
# =========================================================================== #


def test_auth_me_01__nothing_sent_returns_same_user(db, S, dr):
    """AUTH-ME-01 — nothing sent: the same user, no commit, no rollback, no Cloudinary call.
    Rules: update_current_user R1."""
    # [claude] AUTH-ME-01
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    X, _X_ID = extra_row(db, S)
    with spies(db) as (cm, rb):
        result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate())
    # Then 1
    assert result is S.UA
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert dr.call_count == 0
    # Then 5
    assert X in db


def test_auth_me_02__new_name_saved_other_fields_stay(db, S, dr):
    """AUTH-ME-02 — a new name is saved, other fields stay.
    Rules: update_current_user R2, R3, R9."""
    # [claude] AUTH-ME-02
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    c_stamp(db, S, VEC_())
    commit_point(db)
    with spies(db) as (cm, _rb):
        result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(name="Ann Smith"))
    # Then 1
    assert result.id == S.UA.id
    assert result.name == "Ann Smith"
    # Then 2
    assert not_expired(result)
    # Then 3
    assert cm.call_count == 1
    # Then 4
    row = c_committed_ua(db, S)
    assert row.name == "Ann Smith"
    assert row.timezone == "Asia/Dhaka"
    assert row.saved_stamp == VEC


def test_auth_me_03__name_null_leaves_name(db, S, dr):
    """AUTH-ME-03 — name null leaves the name as it is.
    Rules: update_current_user R3."""
    # [claude] AUTH-ME-03
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(name=None))
    # Then 1
    assert result.id == S.UA.id
    # Then 2
    assert reread(db, Profile, S.UA.id).name == "Ann Lee"


@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_auth_me_04__whitespace_only_name_refused_by_schema(db, S, dr):
    """AUTH-ME-04 — a whitespace-only name is refused by the schema.
    Rules: update_current_user R3a [BUG-1406]."""
    # [claude] AUTH-ME-04
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProfileMeUpdate(name="   ")


@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_auth_me_05__empty_name_refused_by_schema(db, S, dr):
    """AUTH-ME-05 — an empty name is refused by the schema.
    Rules: update_current_user R3a [BUG-1406]."""
    # [claude] AUTH-ME-05
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProfileMeUpdate(name="")


@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_auth_me_06__name_stored_trimmed_inner_spaces_kept(db, S, dr):
    """AUTH-ME-06 — the name is stored trimmed, inner spaces kept.
    Rules: update_current_user R3a [BUG-1406]."""
    # [claude] AUTH-ME-06
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(name="  Ann  Smith  "))
    # Then 1
    assert result.id == S.UA.id
    # Then 2
    assert reread(db, Profile, S.UA.id).name == "Ann  Smith"


def test_auth_me_07__new_time_zone_saved_name_stays(db, S, dr):
    """AUTH-ME-07 — a new time zone is saved, the name stays.
    Rules: update_current_user R2, R4."""
    # [claude] AUTH-ME-07
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone="Europe/London"))
    # Then 1
    assert result.timezone == "Europe/London"
    # Then 2
    row = c_committed_ua(db, S)
    assert row.timezone == "Europe/London"
    assert row.name == "Ann Lee"


def test_auth_me_08__time_zone_null_clears_it(db, S, dr):
    """AUTH-ME-08 — time zone null clears it.
    Rules: update_current_user R4."""
    # [claude] AUTH-ME-08
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone=None))
    # Then 1
    assert result.timezone is None
    # Then 2
    assert c_committed_ua(db, S).timezone is None


def test_auth_me_09__empty_time_zone_clears_it(db, S, dr):
    """AUTH-ME-09 — an empty time zone clears it.
    Rules: update_current_user R4."""
    # [claude] AUTH-ME-09
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone=""))
    # Then 1
    assert result.timezone is None
    # Then 2
    assert c_committed_ua(db, S).timezone is None


def test_auth_me_10__whitespace_time_zone_clears_it(db, S, dr):
    """AUTH-ME-10 — a whitespace time zone clears it.
    Rules: update_current_user R4."""
    # [claude] AUTH-ME-10
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone="   "))
    # Then 1
    assert result.timezone is None
    # Then 2
    assert c_committed_ua(db, S).timezone is None


def test_auth_me_11__removing_image_stamp_deletes_users_picture(db, S, dr):
    """AUTH-ME-11 — removing an image stamp clears it and deletes the user's picture.
    Rules: update_current_user R5."""
    # [claude] AUTH-ME-11
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert c_committed_ua(db, S).saved_stamp is None
    # Then 3
    assert dr.call_count == 1
    # Then 4
    assert dr.call_args.kwargs["public_id"] == OWN(S.UA)


def test_auth_me_12__removing_vector_stamp_deletes_nothing(db, S, dr):
    """AUTH-ME-12 — removing a vector stamp deletes nothing in Cloudinary.
    Rules: update_current_user R5."""
    # [claude] AUTH-ME-12
    c_stamp(db, S, VEC_())
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert c_committed_ua(db, S).saved_stamp is None
    # Then 3
    assert dr.call_count == 0


def test_auth_me_13__removing_without_stamp_deletes_nothing(db, S, dr):
    """AUTH-ME-13 — removing when there is no stamp deletes nothing.
    Rules: update_current_user R5."""
    # [claude] AUTH-ME-13
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert dr.call_count == 0


def test_auth_me_14__vector_stamp_stored_cleaned(db, S, dr):
    """AUTH-ME-14 — a vector stamp is stored in its cleaned form.
    Rules: update_current_user R6."""
    # [claude] AUTH-ME-14
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp={"kind": "vector", "extra": 1, "strokes": [{"color": "#000000", "width": 0.5, "points": [], "junk": "x"}], "viewBox": {"width": 100, "height": 50}}))
    # Then 1
    assert result.saved_stamp == VEC
    # Then 2
    assert c_committed_ua(db, S).saved_stamp == VEC
    # Then 3
    assert dr.call_count == 0


def test_auth_me_15__own_minted_image_stamp_stored(db, S, dr):
    """AUTH-ME-15 — the user's own minted image stamp is stored.
    Rules: update_current_user R6, R6a (the form that stays accepted)."""
    # [claude] AUTH-ME-15
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UA))))
    # Then 1
    assert set(result.saved_stamp) == {"kind", "public_id", "url", "width", "height"}
    # Then 2
    stamp = c_committed_ua(db, S).saved_stamp
    assert stamp["kind"] == "image"
    assert stamp["public_id"] == OWN(S.UA)
    assert stamp["width"] == 10
    assert stamp["height"] == 10
    # Then 3
    assert dr.call_count == 0


@pytest.mark.xfail(strict=True, reason=BUG_1866)
def test_auth_me_16__stored_url_is_server_built(db, S, dr):
    """AUTH-ME-16 — the stored url is the one the server builds.
    Rules: update_current_user R8 [BUG-1866]."""
    # [claude] AUTH-ME-16
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UA))))
    # Then 1
    assert result.saved_stamp["public_id"] == OWN(S.UA)
    # Then 2
    assert result.saved_stamp["url"].startswith(SRV)
    # Then 3
    stamp = c_committed_ua(db, S).saved_stamp
    assert stamp["url"].startswith(SRV)
    # Then 4
    assert OWN(S.UA) in stamp["url"]
    # Then 5
    assert "https://tracker.example/p.png" not in str(stamp)


def test_auth_me_17__invalid_kind_refused_name_not_saved(db, S, dr):
    """AUTH-ME-17 — an invalid stamp kind is refused and the name sent with it is not saved.
    Rules: update_current_user R6, R9 (TC3), Errors."""
    # [claude] AUTH-ME-17
    c_stamp(db, S, IMG(OWN(S.UA)))
    before = commit_point(db, S.UA)
    _X, X_ID = extra_row(db, S)
    # Then 1
    with pytest.raises(ValueError) as exc:
        with spies(db) as (_cm, rb):
            svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(name="Ann Smith", saved_stamp={"kind": "sticker"}))
    assert str(exc.value) == KIND_MSG
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert dr.call_count == 0
    # Then 4
    assert x_count(db, X_ID) == 0
    # Then 5
    assert snap(db, S.UA) == before[S.UA]


def test_auth_me_18__image_width_zero_is_validation_error(db, S, dr):
    """AUTH-ME-18 — an image stamp of width 0 is a validation error and nothing is saved.
    Rules: update_current_user R6."""
    # [claude] AUTH-ME-18
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(PydanticValidationError):
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone="Europe/London", saved_stamp={"kind": "image", "public_id": OWN(S.UA), "url": "https://tracker.example/p.png", "width": 0, "height": 10}))
    # Then 2
    assert dr.call_count == 0
    # Then 3
    assert snap(db, S.UA) == before[S.UA]


@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_auth_me_19__higher_id_users_stamp_refused(db, S, dr):
    """AUTH-ME-19 — another (higher-id) user's stamp id is refused.
    Rules: update_current_user R6a [BUG-1864]."""
    # [claude] AUTH-ME-19
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UB))))
    assert str(exc.value) == FOREIGN
    # Then 2
    assert snap(db, S.UA) == before[S.UA]


@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_auth_me_20__lower_id_users_stamp_refused(db, S, dr):
    """AUTH-ME-20 — another (lower-id) user's stamp id is refused.
    Rules: update_current_user R6a [BUG-1864]."""
    # [claude] AUTH-ME-20
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.U0))))
    assert str(exc.value) == FOREIGN
    # Then 2
    assert snap(db, S.UA) == before[S.UA]


@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_auth_me_21__attachment_id_refused(db, S, dr):
    """AUTH-ME-21 — an attachment's id is refused.
    Rules: update_current_user R6a [BUG-1864]."""
    # [claude] AUTH-ME-21
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(ATT)))
    assert str(exc.value) == FOREIGN
    # Then 2
    assert snap(db, S.UA) == before[S.UA]


@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_auth_me_22__production_form_foreign_in_development(db, S, dr):
    """AUTH-ME-22 — the production form is foreign in development.
    Rules: update_current_user R6a [BUG-1864]."""
    # [claude] AUTH-ME-22
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(f"profiles/{S.UA.id}/stamp-{TOKEN}")))
    assert str(exc.value) == FOREIGN
    # Then 2
    assert snap(db, S.UA) == before[S.UA]


@pytest.mark.xfail(strict=True, reason=BUG_1864)
def test_auth_me_23__own_id_with_trailing_newline_refused(db, S, dr):
    """AUTH-ME-23 — the own id with a trailing newline is refused.
    Rules: update_current_user R6a [BUG-1864]."""
    # [claude] AUTH-ME-23
    before = commit_point(db, S.UA)
    # Then 1
    with pytest.raises(ValueError) as exc:
        svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UA) + "\n")))
    assert str(exc.value) == FOREIGN
    # Then 2
    assert snap(db, S.UA) == before[S.UA]


def test_auth_me_24__image_replaced_by_image_deletes_old(db, S, dr):
    """AUTH-ME-24 — replacing an image with another image deletes the old picture.
    Rules: update_current_user R7."""
    # [claude] AUTH-ME-24
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN2(S.UA))))
    # Then 1
    assert result.saved_stamp["public_id"] == OWN2(S.UA)
    # Then 2
    assert c_committed_ua(db, S).saved_stamp["public_id"] == OWN2(S.UA)
    # Then 3
    assert dr.call_count == 1
    # Then 4
    assert dr.call_args.kwargs["public_id"] == OWN(S.UA)


def test_auth_me_25__same_image_again_deletes_nothing(db, S, dr):
    """AUTH-ME-25 — the same image again deletes nothing.
    Rules: update_current_user R7."""
    # [claude] AUTH-ME-25
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UA))))
    # Then 1
    assert result.saved_stamp["public_id"] == OWN(S.UA)
    # Then 2
    assert dr.call_count == 0


def test_auth_me_26__image_replaced_by_drawing_saves_drawing(db, S, dr):
    """AUTH-ME-26 — replacing an image with a drawing saves the drawing.
    Rules: update_current_user R6, R7b (part independent of BUG-2568)."""
    # [claude] AUTH-ME-26
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=VEC_()))
    # Then 1
    assert result.saved_stamp == VEC
    # Then 2
    assert c_committed_ua(db, S).saved_stamp == VEC


@pytest.mark.xfail(strict=True, reason=BUG_2568)
def test_auth_me_27__image_replaced_by_drawing_deletes_old_picture(db, S, dr):
    """AUTH-ME-27 — replacing an image with a drawing deletes the old picture.
    Rules: update_current_user R7b [BUG-2568]."""
    # [claude] AUTH-ME-27
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=VEC_()))
    # Then 1
    assert result.saved_stamp == VEC
    # Then 2
    assert dr.call_count == 1
    # Then 3
    assert dr.call_args.kwargs["public_id"] == OWN(S.UA)


def test_auth_me_28__removing_foreign_named_stamp_still_clears(db, S, dr):
    """AUTH-ME-28 — removing a stamp that names another user's picture still clears it.
    Rules: update_current_user R5, R7a (part independent of BUG-1865)."""
    # [claude] AUTH-ME-28
    c_stamp(db, S, IMG(OWN(S.UB)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert c_committed_ua(db, S).saved_stamp is None


@pytest.mark.xfail(strict=True, reason=BUG_1865)
def test_auth_me_29__other_users_picture_never_deleted(db, S, dr):
    """AUTH-ME-29 — another user's picture named by an old stamp is never deleted.
    Rules: update_current_user R7a [BUG-1865]."""
    # [claude] AUTH-ME-29
    c_stamp(db, S, IMG(OWN(S.UB)))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert dr.call_count == 0


@pytest.mark.xfail(strict=True, reason=BUG_1865)
def test_auth_me_30__attachment_named_by_old_stamp_not_deleted_on_replace(db, S, dr):
    """AUTH-ME-30 — an attachment named by an old stamp is not deleted on replace.
    Rules: update_current_user R7, R7a [BUG-1865]."""
    # [claude] AUTH-ME-30
    c_stamp(db, S, IMG(ATT))
    commit_point(db)
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(S.UA))))
    # Then 1
    assert result.saved_stamp["public_id"] == OWN(S.UA)
    # Then 2
    assert dr.call_count == 0


def test_auth_me_31__failing_commit_keeps_old_stamp(db, S, dr):
    """AUTH-ME-31 — a failing commit keeps the old stamp.
    Rules: update_current_user R9 (TC4)."""
    # [claude] AUTH-ME-31
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, Profile, S.UA.id).saved_stamp == IMG(OWN(S.UA))


@pytest.mark.xfail(strict=True, reason=BUG_2562)
def test_auth_me_32__failing_commit_deletes_no_picture(db, S, dr):
    """AUTH-ME-32 — a failing commit deletes no picture.
    Rules: update_current_user R10 [BUG-2562]."""
    # [claude] AUTH-ME-32
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback):
            svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    assert str(exc.value) == "boom"
    # Then 2
    assert reread(db, Profile, S.UA.id).saved_stamp == IMG(OWN(S.UA))
    # Then 3
    assert dr.call_count == 0


@pytest.mark.xfail(strict=True, reason=BUG_2562)
def test_auth_me_33__picture_deleted_after_commit(db, S, dr):
    """AUTH-ME-33 — the picture is deleted after the commit.
    Rules: update_current_user R10 [BUG-2562]."""
    # [claude] AUTH-ME-33
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    order = []
    dr.side_effect = lambda *a, **k: order.append("destroy") or {"result": "ok"}
    real_commit = db.commit

    def commit_spy(*a, **k):
        order.append("commit")
        return real_commit(*a, **k)

    with patch.object(db, "commit", wraps=commit_spy):
        result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert order == ["commit", "destroy"]


def test_auth_me_34__failed_cloudinary_delete_never_fails_change(db, S, dr):
    """AUTH-ME-34 — a failed Cloudinary delete never fails the change.
    Rules: update_current_user R10 (BUG-1713 rule, holds today)."""
    # [claude] AUTH-ME-34
    c_stamp(db, S, IMG(OWN(S.UA)))
    commit_point(db)
    dr.side_effect = RuntimeError("network down")
    result = svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(saved_stamp=None))
    # Then 1
    assert result.saved_stamp is None
    # Then 2
    assert c_committed_ua(db, S).saved_stamp is None
    # Then 3
    assert dr.call_count == 1


def test_auth_me_35__failing_refresh_keeps_change(db, S, dr):
    """AUTH-ME-35 — a failing re-read after the commit keeps the change.
    Rules: update_current_user R9 (TC5)."""
    # [claude] AUTH-ME-35
    S.UA.timezone = "Asia/Dhaka"
    db.flush()
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.update_current_user(db, user=S.UA, update=ProfileMeUpdate(timezone="Europe/London"))
    assert str(exc.value) == "boom"
    # Then 2
    assert c_committed_ua(db, S).timezone == "Europe/London"
