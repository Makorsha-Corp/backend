"""Unit tests for app/services/mobile_upload_service.py.

Implements tests/unit/services/mobile_upload_service.cases.md (revision 3),
one test per card, in card order. Real Postgres session (`db` fixture), rolled
back after each test.

Externals patched in every test (fixture `CL`, Conventions "Settings and time"
and "Cloudinary"): the settings on `app.core.config.settings`; `utcnow` of the
mobile manager and of `app.dao.mobile_upload_session`; `uuid.uuid4`,
`time.time` and `secrets.token_urlsafe` through the mobile manager module; the
six Cloudinary functions as imported in `app.managers.mobile_upload_session_manager`
and the four as imported in `app.managers.attachment_manager`, each with
`autospec=True`. Nothing touches the network.

Standing rows are fixture `R` (`R.W1`, `R.UG`, `R.P1` ...). Every test runs
`commit_point(db)` after its last Given line: `db.commit()`, which only releases
a savepoint under the `db` fixture, so the service's rollback cannot remove the
Given rows. `# Then N` marks the checks of Then line N.
"""

import hashlib
import inspect
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.managers.attachment_manager import (
    AttachmentLimitError,
    AttachmentNotFoundError,
)
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.attachment_link import AttachmentLink
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.mobile_upload_session import MobileUploadSession
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.mobile_upload import (
    MobileUploadPromoteRequest,
    MobileUploadPublicConfirmRequest,
    MobileUploadPublicSignRequest,
    MobileUploadSessionCreateRequest,
)
from app.services.mobile_upload_service import (
    AttachmentConfirmError,
    AttachmentValidationError,
    CloudinaryNotConfiguredError,
    MobileUploadSessionError,
    MobileUploadSessionNotFoundError,
    mobile_upload_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = mobile_upload_service"
svc = mobile_upload_service
MOD = "app.managers.mobile_upload_session_manager"
AMOD = "app.managers.attachment_manager"

MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)  # noqa: DTZ001  (Conventions: naive)
NOW_UTC = NOW.replace(tzinfo=timezone.utc)
PAST = NOW_UTC - timedelta(days=1)
LATER = NOW_UTC + timedelta(days=1)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
RAW1 = "raw-token-one-0001"
RAW0 = "raw-token-zero-0000"
RAW2 = "raw-token-two-0002"
RAWX = "raw-token-unknown-9"
RAWT = "fixed-raw-token-000"
TOKEN = "0123456789abcdef0123456789abcdef"
STG = "development/ws-0/mobile-staging/0/" + "f" * 32
OLD = "development/ws-0/mobile-staging/0/" + "e" * 32
NOTF = "Upload session not found."
EXPD = "Upload session has expired."
GONE = "Upload session is no longer available."
HASF = "This session already received a file."
GR = {"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000000}
GRA = {
    "resource_type": "image",
    "format": "jpg",
    "bytes": 2048,
    "version": 1700000001,
    "secure_url": "https://res.example/a.jpg",
    "width": 800,
    "height": 600,
    "asset_id": "a" * 32,
    "etag": "e" * 32,
}
SETTINGS = {
    "CLOUDINARY_UPLOAD_ENV": "development",
    "ENVIRONMENT": "development",
    "CLOUDINARY_CLOUD_NAME": "demo-cloud",
    "CLOUDINARY_API_KEY": "123456",
    "CLOUDINARY_API_SECRET": "s3cret",
    "MAX_ATTACHMENTS_PER_ENTITY": 25,
}


# Convention "H(x)"
def H(x):
    return hashlib.sha256(x.encode("utf-8")).hexdigest()


# Convention "TOO(n)"
def TOO(n):
    return "File too large (" + str(n) + " bytes). Maximum is 10485760 bytes."


# Convention "NF(t, i)"
def NF(t, i):
    return t + " " + str(i) + " not found."


# Convention "DEST"
def DEST(R):
    return "development/ws-" + str(R.W1.id) + "/" + TOKEN


# Convention "kw(m)": the call's arguments by the real parameter names, defaults filled in
def kw(m):
    ba = inspect.signature(m).bind(*m.call_args.args, **m.call_args.kwargs)
    ba.apply_defaults()
    return dict(ba.arguments)


# Conventions "CRQ", "PRQ", "SRQ", "CFQ"
def CRQ(t, i, label=None):
    return MobileUploadSessionCreateRequest(
        entity_type=t, entity_id=i, entity_label=label
    )


PRQ = MobileUploadPromoteRequest(file_name=None, note="Front")


def SRQ(tok):
    return MobileUploadPublicSignRequest(
        token=tok, file_name="scan.jpg", mime_type="image/jpeg", file_size=3000
    )


def CFQ(tok):
    return MobileUploadPublicConfirmRequest(token=tok)


# --------------------------------------------------------------------------- #
# Conventions "Settings and time" + "Cloudinary" (every test)
# --------------------------------------------------------------------------- #

CL_NAMES = ("gus", "gr", "dr", "rr", "um", "bsdu", "agr", "adr", "ags", "absdu")


@pytest.fixture(autouse=True)
def CL(monkeypatch):
    """Every patch of the Conventions; `CL.<name>` is the mock, `CL.setting(n, v)` a Given settings line."""
    for name, value in SETTINGS.items():
        monkeypatch.setattr(settings, name, value)
    ns = SimpleNamespace()
    patchers = []

    def start(key, target, **kwargs):
        p = patch(target, **kwargs)
        setattr(ns, key, p.start())
        patchers.append(p)

    start("clock", MOD + ".utcnow", return_value=NOW)
    start("dao_clock", "app.dao.mobile_upload_session.utcnow", return_value=NOW)
    start("uuid", MOD + ".uuid.uuid4", return_value=uuid.UUID(TOKEN))
    start("time", MOD + ".time.time", return_value=1767225600.9)
    start("raw", MOD + ".secrets.token_urlsafe", return_value=RAWT)
    start(
        "gus", MOD + ".generate_upload_signature", autospec=True, return_value="sig-x"
    )
    start("gr", MOD + ".get_resource", autospec=True, return_value=dict(GR))
    start("dr", MOD + ".destroy_resource", autospec=True, return_value={"result": "ok"})
    start("rr", MOD + ".rename_resource", autospec=True, return_value={})
    start(
        "um",
        MOD + ".update_resource_metadata",
        autospec=True,
        return_value={"result": "ok"},
    )
    start(
        "bsdu",
        MOD + ".build_signed_delivery_url",
        autospec=True,
        return_value="https://signed.example/preview",
    )
    start("agr", AMOD + ".get_resource", autospec=True, return_value=dict(GRA))
    start(
        "adr", AMOD + ".destroy_resource", autospec=True, return_value={"result": "ok"}
    )
    start(
        "ags", AMOD + ".generate_upload_signature", autospec=True, return_value="sig-a"
    )
    start(
        "absdu",
        AMOD + ".build_signed_delivery_url",
        autospec=True,
        return_value="https://signed.example/a",
    )

    def setting(name, value):
        monkeypatch.setattr(settings, name, value)

    ns.setting = setting
    yield ns
    for p in reversed(patchers):
        p.stop()


def cl_called(CL):
    """Named check "cl_untouched": the names of the Cloudinary mocks that were called (must be [])."""
    return [n for n in CL_NAMES if getattr(CL, n).called is not False]


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (built in this order, each flushed)
# --------------------------------------------------------------------------- #


def add(db, row):
    db.add(row)
    db.flush()
    return row


# Given row "member(U, role, status="active", ws=W1)"
def member(db, R, u, role, status="active", ws=None):
    ws = ws or R.W1
    return add(
        db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status)
    )


@pytest.fixture
def R(db):
    """Standing rows: W0, W1, W2; U1, U2, UG with W1 memberships (MG = UG's); F0, F1, F9; P1."""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    r = SimpleNamespace()
    r.W0 = make_workspace(db)
    r.W1 = make_workspace(db)
    r.W2 = make_workspace(db)
    r.U1 = make_profile(db, name="Ana Rahman")
    r.U2 = make_profile(db, name="Bilal Khan")
    r.UG = make_profile(db, name="Mia Khan")
    member(db, r, r.U1, "ground-team")
    member(db, r, r.U2, "owner")
    r.MG = member(db, r, r.UG, "ground-team")
    r.F0 = add(
        db, Factory(workspace_id=r.W0.id, name="Factory Zero", abbreviation="F0")
    )
    r.F1 = add(db, Factory(workspace_id=r.W1.id, name="Factory One", abbreviation="F1"))
    r.F9 = add(
        db, Factory(workspace_id=r.W2.id, name="Factory Nine", abbreviation="F9")
    )
    r.P1 = proj(db, r, "Tender")
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def proj(db, R, name, where="W1", private=False, deleted=False):
    """proj / W2 proj; `private`, `deleted` as Conventions."""
    ws = getattr(R, where)
    factory = {"W1": R.F1, "W2": R.F9}[where]
    fields = {
        "workspace_id": ws.id,
        "factory_id": factory.id,
        "name": name,
        "description": "Main",
        "created_by": R.U1.id,
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=R.U1.id)
    return add(db, Project(**fields))


def pmem(db, R, p, u):
    return add(
        db,
        ProjectMember(
            workspace_id=p.workspace_id,
            project_id=p.id,
            user_id=u.id,
            assigned_by=R.U1.id,
        ),
    )


def ticket(db, R, number):
    return add(
        db,
        HelpTicket(
            workspace_id=R.W1.id,
            ticket_number=number,
            title="Printer jam",
            description="It jams",
            created_by=R.U1.id,
        ),
    )


def sess(db, R, kind="sess", where="W1", **over):
    """sess / staged / uploaded (W0 sess, W2 sess via `where`); `over` = the columns after "but". Flushed."""
    fields = {
        "workspace_id": R.W1.id,
        "created_by": R.UG.id,
        "entity_type": "project",
        "entity_id": R.P1.id,
        "entity_label": "Tender",
        "token_hash": H(RAW1),
        "expires_at": LATER,
        "status": "waiting",
    }
    if kind in ("staged", "uploaded"):
        fields.update(
            public_id=STG,
            asset_folder="Dev/x/Mobile Staging/session-0",
            resource_type="image",
            file_name="photo.jpg",
            mime_type="image/jpeg",
            file_size=2048,
        )
    if kind == "uploaded":
        fields.update(status="uploaded", format="jpg", version=1700000000)
    if where == "W0":
        fields.update(workspace_id=R.W0.id, token_hash=H(RAW0))
    if where == "W2":
        fields.update(workspace_id=R.W2.id, token_hash=H(RAW2))
    fields.update(over)
    return add(db, MobileUploadSession(**fields))


def full(db, R, p):
    """full(P): 25 ready attachments, each linked to project P."""
    for i in range(1, 26):
        a = add(
            db,
            Attachment(
                workspace_id=R.W1.id,
                file_name=f"f{i}.jpg",
                mime_type="image/jpeg",
                file_size=1,
                uploaded_by=R.U1.id,
                upload_status="ready",
                public_id=f"full/{i}",
            ),
        )
        add(
            db,
            AttachmentLink(
                workspace_id=R.W1.id,
                attachment_id=a.id,
                entity_type="project",
                entity_id=p.id,
                linked_by=R.U1.id,
            ),
        )


# --------------------------------------------------------------------------- #
# Commit point and named checks
# --------------------------------------------------------------------------- #


def commit_point(db):
    """Commit point: releases the savepoint holding the Given rows."""
    db.commit()


def pending_x(db, R):
    """ "pending X": a W2 factory added and flushed after the commit point; returns X_ID."""
    x = add(db, Factory(workspace_id=R.W2.id, name="Factory X", abbreviation="FX"))
    return x.id


def x_count(db, x_id):
    """x_gone = 0, x_kept = 1."""
    return db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": x_id})


def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def snap(db, row):
    """Snapshot for unchanged(X), taken at the commit point."""
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def unchanged(db, model, before):
    db.expire_all()
    fresh = db.get(model, before["id"])
    return (
        fresh is not None and {k: getattr(fresh, k) for k in _columns(model)} == before
    )


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def counts(db):
    """ "nothing written": row counts of the five tables (all workspaces)."""
    return tuple(
        db.scalar(text(f"SELECT count(*) FROM {t}"))
        for t in (
            "mobile_upload_sessions",
            "attachments",
            "attachment_links",
            "attachment_ledger",
            "project_events",
        )
    )


def count(db, table, cond, **params):
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {cond}"), params)


def att_by_pid(db, pid):
    db.expire_all()
    return db.query(Attachment).filter(Attachment.public_id == pid).one()


def ledger_rows(db, pid):
    a = att_by_pid(db, pid)
    return (
        db.query(AttachmentLedger)
        .filter(AttachmentLedger.attachment_id == a.id)
        .order_by(AttachmentLedger.id)
        .all()
    )


def ledger_types(db, pid):
    return [r.transaction_type for r in ledger_rows(db, pid)]


@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield SimpleNamespace(cm=cm, rb=rb)


@contextmanager
def failing_commit(db):
    """Use inside `with pytest.raises(RuntimeError) as exc:`."""
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield SimpleNamespace(rb=rb)


@contextmanager
def order_log(db, CL):
    """ "order log": dr appends "dr"; db.commit appends "commit"."""
    order = []

    def _dr(*args, **kwargs):
        order.append("dr")
        return {"result": "ok"}

    CL.dr.side_effect = _dr
    real = db.commit
    with patch.object(
        db, "commit", side_effect=lambda: (order.append("commit"), real())[1]
    ):
        yield order


@contextmanager
def event_log(db, CL):
    """ "event log": SQL statements and the dr / rr / um / agr calls, in order."""
    ev = []

    def rec(conn, cursor, statement, params, context, executemany):
        ev.append(("sql", statement))

    def logged(name, value):
        def _side(*args, **kwargs):
            ev.append(("cl", name))
            return value

        return _side

    CL.dr.side_effect = logged("dr", {"result": "ok"})
    CL.rr.side_effect = logged("rr", {})
    CL.um.side_effect = logged("um", {"result": "ok"})
    CL.agr.side_effect = logged("agr", dict(GRA))
    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield ev
    finally:
        event.remove(conn, "before_cursor_execute", rec)


def first_read(ev):
    """ "first_read": index of the first SELECT naming mobile_upload_sessions."""
    return next(
        i
        for i, (k, v) in enumerate(ev)
        if k == "sql"
        and v.lstrip().upper().startswith("SELECT")
        and "MOBILE_UPLOAD_SESSIONS" in v.lstrip().upper()
    )


def acted_before(ev, i):
    return any(
        k == "cl" or v.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for k, v in ev[:i]
    )


def warned(caplog, p):
    return any(
        r.levelno == logging.WARNING and p in r.getMessage() for r in caplog.records
    )


XF2130 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2130: QR session opened for a missing / deleted / other-workspace record",
)
XF2131 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2131: QR session opened for a record the caller may not open",
)
XF2134 = pytest.mark.xfail(
    strict=True, reason="BUG-2134: attach does not re-check the record (PR-1 / PR-2)"
)
XF2137 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2137: the cleared session of an oversized phone file is rolled back, not saved",
)
XF2139 = pytest.mark.xfail(
    strict=True, reason="BUG-2139: promote / cancel read the session without a row lock"
)
XF2204 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2204: a phone file whose verification fails after the move is lost",
)
XF2136 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2136: a failed delete of a staged file is swallowed with no log",
)
XF2205 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2205: cancel and re-sign delete the staged file before the change is saved",
)


# =========================================================================== #
# create_session
# =========================================================================== #


# [claude] MUSV-C-01
def test_musv_c_01__a_session_is_created_committed_and_answered_with_the_raw_token(
    db, R
):
    """MUSV-C-01 — a session is created, committed and answered with the raw token.
    Rules: create_session R1, TC1."""
    commit_point(db)
    result = svc.create_session(
        db, workspace=R.W1, user=R.UG, payload=CRQ("project", R.P1.id)
    )
    # Then 1
    assert type(result).__name__ == "MobileUploadSessionCreateResponse"
    # Then 2
    assert result.token == RAWT
    assert result.entity_label == "Tender"
    assert result.session_id is not None
    # Then 3
    db.rollback()
    row = reread(db, MobileUploadSession, result.session_id)
    assert row.workspace_id == R.W1.id
    assert row.created_by == R.UG.id
    assert row.entity_type == "project"
    assert row.entity_id == R.P1.id
    # Then 4
    assert row.status == "waiting"
    assert row.entity_label == "Tender"
    assert row.token_hash == H(RAWT)
    assert row.public_id is None


# [claude] MUSV-C-02
def test_musv_c_02__the_clients_label_reaches_the_manager_trimmed(db, R):
    """MUSV-C-02 — the client's label reaches the manager trimmed.
    Rules: create_session R1 (payload passed down)."""
    commit_point(db)
    result = svc.create_session(
        db, workspace=R.W1, user=R.UG, payload=CRQ("project", R.P1.id, "  Front door  ")
    )
    # Then 1
    assert result.entity_label == "Front door"
    # Then 2
    db.rollback()
    row = reread(db, MobileUploadSession, result.session_id)
    assert row.entity_label == "Front door"


# [claude] MUSV-C-03
def test_musv_c_03__a_database_error_rolls_back_and_discards_other_pending_changes(
    db, R
):
    """MUSV-C-03 — a database error rolls back and discards other pending changes.
    Rules: create_session R2, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = pending_x(db, R)
    ghost = SimpleNamespace(id=MISSING, name="Ghost", is_platform_admin=False)
    # Then 1
    with pytest.raises(IntegrityError), spies(db) as sp:
        svc.create_session(
            db, workspace=R.W1, user=ghost, payload=CRQ("project", R.P1.id)
        )
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert sp.rb.call_count >= 1
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert db.execute(text("SELECT 1")).scalar() == 1


# [claude] MUSV-C-04
def test_musv_c_04__a_failing_commit_saves_no_session(db, R):
    """MUSV-C-04 — a failing commit saves no session.
    Rules: create_session R2, TC4."""
    commit_point(db)
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.create_session(
            db, workspace=R.W1, user=R.UG, payload=CRQ("project", R.P1.id)
        )
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] MUSV-C-05
@XF2130
def test_musv_c_05__a_deleted_project_is_refused_as_not_found_nothing_written(db, R):
    """MUSV-C-05 — a deleted project is refused as not found; nothing written.
    Rules: create_session R2 [BUG-2130]; PR-1."""
    p2 = proj(db, R, "Bridge", deleted=True)
    commit_point(db)
    p2_id = p2.id
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.create_session(db, workspace=R.W1, user=R.UG, payload=CRQ("project", p2_id))
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] MUSV-C-06
@XF2130
def test_musv_c_06__a_w2_project_is_refused_as_not_found_nothing_written(db, R):
    """MUSV-C-06 — a W2 project is refused as not found; nothing written.
    Rules: create_session R2 [BUG-2130]; HR-16."""
    p2 = proj(db, R, "Bridge", where="W2")
    commit_point(db)
    p2_id = p2.id
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.create_session(db, workspace=R.W1, user=R.UG, payload=CRQ("project", p2_id))
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] MUSV-C-07
@XF2131
def test_musv_c_07__a_private_project_the_caller_may_not_open_is_refused(db, R):
    """MUSV-C-07 — a private project the caller may not open is refused.
    Rules: create_session R2 [BUG-2131]; PR-2, PR-5."""
    p2 = proj(db, R, "Bridge", private=True)
    commit_point(db)
    p2_id = p2.id
    before = counts(db)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.create_session(db, workspace=R.W1, user=R.UG, payload=CRQ("project", p2_id))
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert x_count(db, x_id) == 0


# [claude] MUSV-C-08
@XF2131
def test_musv_c_08__membership_of_another_private_project_does_not_open_this_one(db, R):
    """MUSV-C-08 — membership of another private project does not open this one.
    Rules: create_session R2 [BUG-2131]; PR-2 (grant held on a different record)."""
    p2 = proj(db, R, "Bridge", private=True)
    p3 = proj(db, R, "Canal", private=True)
    pmem(db, R, p3, R.UG)
    commit_point(db)
    p2_id = p2.id
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.create_session(db, workspace=R.W1, user=R.UG, payload=CRQ("project", p2_id))
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] MUSV-C-09
@XF2131
def test_musv_c_09__an_owner_role_held_only_in_w0_does_not_open_another_members_w1_ticket(
    db, R
):
    """MUSV-C-09 — an owner role held only in W0 does not open another member's W1 ticket.
    Rules: create_session R2 [BUG-2131]; PR-2, PR-5 (grant held in a different workspace)."""
    member(db, R, R.UG, "owner", ws=R.W0)
    t1 = ticket(db, R, "HT-1")
    commit_point(db)
    t1_id = t1.id
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.create_session(
            db, workspace=R.W1, user=R.UG, payload=CRQ("support_ticket", t1_id)
        )
    # Then 2
    assert str(exc.value) == NF("support_ticket", t1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] MUSV-C-10
def test_musv_c_10__a_project_member_opens_a_session_for_the_private_project(db, R):
    """MUSV-C-10 — a project member opens a session for the private project.
    Rules: create_session R1; PR-2, PR-5."""
    p2 = proj(db, R, "Bridge", private=True)
    pmem(db, R, p2, R.UG)
    commit_point(db)
    p2_id = p2.id
    result = svc.create_session(
        db, workspace=R.W1, user=R.UG, payload=CRQ("project", p2_id)
    )
    # Then 1
    assert result.entity_label == "Bridge"
    # Then 2
    db.rollback()
    row = reread(db, MobileUploadSession, result.session_id)
    assert row.created_by == R.UG.id
    assert row.entity_id == p2_id


# =========================================================================== #
# get_session
# =========================================================================== #


# [claude] MUSV-GS-01
def test_musv_gs_01__the_callers_own_session_is_answered_without_a_cloudinary_id(db, R):
    """MUSV-GS-01 — the caller's own session is answered without a Cloudinary id.
    Rules: get_session R1."""
    s = sess(db, R)
    commit_point(db)
    s_id = s.id
    result = svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id)
    # Then 1
    assert type(result).__name__ == "MobileUploadSessionResponse"
    # Then 2
    assert result.id == s_id
    assert result.status == "waiting"
    assert result.entity_label == "Tender"
    assert result.entity_id == R.P1.id
    # Then 3
    assert result.preview_url is None
    assert "public_id" not in result.model_dump()


# [claude] MUSV-GS-02
def test_musv_gs_02__an_unknown_id_is_not_found(db, R):
    """MUSV-GS-02 — an unknown id is not found.
    Rules: get_session R2."""
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=MISSING)
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GS-03
def test_musv_gs_03__another_members_session_is_not_found(db, R):
    """MUSV-GS-03 — another member's session is not found.
    Rules: get_session R2."""
    s = sess(db, R, created_by=R.U1.id)
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s.id)
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GS-04
def test_musv_gs_04__the_callers_w0_session_is_not_found_from_w1(db, R):
    """MUSV-GS-04 — the caller's W0 session is not found from W1.
    Rules: get_session R2; HR-16."""
    s = sess(db, R, where="W0")
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s.id)
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GS-05
def test_musv_gs_05__the_callers_w2_session_is_not_found_from_w1(db, R):
    """MUSV-GS-05 — the caller's W2 session is not found from W1.
    Rules: get_session R2; HR-16."""
    s = sess(db, R, where="W2")
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s.id)
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GS-06
def test_musv_gs_06__an_expired_waiting_session_expired_in_memory_only(db, R):
    """MUSV-GS-06 — an expired waiting session: "expired" in memory only, nothing rolled back or saved.
    Rules: get_session R2 (D6), TC6."""
    s = sess(db, R, expires_at=PAST)
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.get_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id)
    # Then 2
    assert str(exc.value) == EXPD
    # Then 3
    assert sp.cm.called is False
    assert sp.rb.called is False
    # Then 4
    assert s in db.dirty
    assert s.status == "expired"
    # Then 5
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "waiting"


# [claude] MUSV-GS-07
def test_musv_gs_07__a_poll_neither_commits_nor_rolls_back_pending_changes_stay(db, R):
    """MUSV-GS-07 — a poll neither commits nor rolls back; pending changes stay.
    Rules: get_session R2, TC6."""
    s = sess(db, R)
    commit_point(db)
    s_id = s.id
    x_id = pending_x(db, R)
    R.F9.name = "Factory Edited"
    with spies(db) as sp:
        result = svc.get_session(
            db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id
        )
    # Then 1
    assert result.id == s_id
    # Then 2
    assert sp.cm.called is False
    assert sp.rb.called is False
    # Then 3
    assert R.F9 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert x_count(db, x_id) == 1
    # Then 5
    db.rollback()
    assert x_count(db, x_id) == 0


# =========================================================================== #
# cancel_session
# =========================================================================== #


# [claude] MUSV-CN-01
def test_musv_cn_01__an_uploaded_session_is_cancelled_and_committed_its_staged_file_deleted(
    db, R, CL
):
    """MUSV-CN-01 — an uploaded session is cancelled and committed; its staged file deleted.
    Rules: cancel_session R3, TC1."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    result = svc.cancel_session(
        db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id
    )
    # Then 1
    assert type(result).__name__ == "MobileUploadSessionResponse"
    assert result.id == s_id
    assert result.status == "cancelled"
    # Then 2
    assert CL.dr.call_count == 1
    assert kw(CL.dr)["public_id"] == STG
    # Then 3
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "cancelled"


# [claude] MUSV-CN-02
def test_musv_cn_02__a_consumed_session_is_answered_unchanged_nothing_deleted(
    db, R, CL
):
    """MUSV-CN-02 — a consumed session is answered unchanged; nothing deleted.
    Rules: cancel_session R3."""
    s = sess(db, R, "uploaded", status="consumed", public_id=None)
    commit_point(db)
    before = snap(db, s)
    result = svc.cancel_session(
        db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=before["id"]
    )
    # Then 1
    assert result.status == "consumed"
    # Then 2
    assert CL.dr.called is False
    # Then 3
    assert unchanged(db, MobileUploadSession, before)


# [claude] MUSV-CN-03
def test_musv_cn_03__an_unknown_id_rolls_back_and_discards_pending_changes(db, R):
    """MUSV-CN-03 — an unknown id rolls back and discards pending changes.
    Rules: cancel_session R2, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.cancel_session(
            db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=MISSING
        )
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert sp.rb.call_count >= 1
    assert sp.cm.called is False
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] MUSV-CN-04
def test_musv_cn_04__another_members_session_is_not_found_and_stays_as_it_was(
    db, R, CL
):
    """MUSV-CN-04 — another member's session is not found and stays as it was.
    Rules: cancel_session R1, R2."""
    s = sess(db, R, "uploaded", created_by=R.U1.id)
    commit_point(db)
    before = snap(db, s)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.cancel_session(
            db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=before["id"]
        )
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before)
    # Then 5
    assert cl_called(CL) == []


# [claude] MUSV-CN-05
def test_musv_cn_05__an_expired_waiting_session_is_refused_and_expired_is_rolled_back(
    db, R
):
    """MUSV-CN-05 — an expired waiting session is refused and "expired" is rolled back.
    Rules: cancel_session R2 (D6)."""
    s = sess(db, R, expires_at=PAST)
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.cancel_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id)
    # Then 2
    assert str(exc.value) == EXPD
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert sp.rb.call_count >= 1
    assert sp.cm.called is False
    # Then 5
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "waiting"


# [claude] MUSV-CN-06
@XF2139
def test_musv_cn_06__cancels_first_read_of_the_session_is_locked_before_anything_acts(
    db, R, CL
):
    """MUSV-CN-06 — cancel's first read of the session is locked, before anything acts.
    Rules: cancel_session R1 [BUG-2139]; HR-10."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id, w1_id, ug_id = s.id, R.W1.id, R.UG.id
    with event_log(db, CL) as ev:
        result = svc.cancel_session(
            db, workspace_id=w1_id, user_id=ug_id, session_id=s_id
        )
    # Then 1
    assert result.status == "cancelled"
    # Then 2
    assert "FOR UPDATE" in ev[first_read(ev)][1].upper()
    # Then 3
    assert acted_before(ev, first_read(ev)) is False


# [claude] MUSV-CN-07
def test_musv_cn_07__a_failing_commit_keeps_the_session_uploaded_with_its_file(db, R):
    """MUSV-CN-07 — a failing commit keeps the session uploaded with its file.
    Rules: cancel_session R3, R4, TC4."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.cancel_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id)
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    row = reread(db, MobileUploadSession, s_id)
    assert row.status == "uploaded"
    assert row.public_id == STG
    # Then 4
    assert counts(db) == before


# [claude] MUSV-CN-08
@XF2205
def test_musv_cn_08__a_failing_commit_never_deletes_the_staged_file(db, R, CL):
    """MUSV-CN-08 — a failing commit never deletes the staged file.
    Rules: cancel_session R3 [BUG-2205]."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db):
        svc.cancel_session(db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id)
    assert str(exc.value) == "boom"
    # Then 2
    assert reread(db, MobileUploadSession, s_id).public_id == STG
    # Then 3
    assert CL.dr.called is False


# [claude] MUSV-CN-09
@XF2205
def test_musv_cn_09__on_success_the_commit_comes_before_the_staged_files_delete(
    db, R, CL
):
    """MUSV-CN-09 — on success the commit comes before the staged file's delete.
    Rules: cancel_session R3 [BUG-2205]."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    with order_log(db, CL) as order:
        result = svc.cancel_session(
            db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id
        )
    # Then 1
    assert result.status == "cancelled"
    # Then 2
    assert order.count("dr") == 1
    assert "commit" in order
    # Then 3
    assert order.index("commit") < order.index("dr")


# [claude] MUSV-CN-10
def test_musv_cn_10__a_raising_delete_after_the_commit_is_swallowed_the_cancel_is_saved(
    db, R, CL
):
    """MUSV-CN-10 — a raising delete after the commit is swallowed; the cancel is saved and answered.
    Rules: cancel_session R3a [BUG-2205] (part that holds today)."""
    s = sess(db, R, "uploaded")
    CL.dr.side_effect = RuntimeError("down")
    commit_point(db)
    s_id = s.id
    result = svc.cancel_session(
        db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id
    )
    # Then 1
    assert result.status == "cancelled"
    # Then 2
    assert CL.dr.call_count == 1
    # Then 3
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "cancelled"


# [claude] MUSV-CN-11
@XF2136
def test_musv_cn_11__that_delete_error_is_logged_as_a_warning_naming_the_staged_file(
    db, R, CL, caplog
):
    """MUSV-CN-11 — that delete error is logged as a WARNING naming the staged file.
    Rules: cancel_session R3a [BUG-2205] with manager _destroy_staging_asset R3 [BUG-2136]."""
    s = sess(db, R, "uploaded")
    CL.dr.side_effect = RuntimeError("down")
    caplog.set_level(logging.WARNING)
    commit_point(db)
    s_id = s.id
    result = svc.cancel_session(
        db, workspace_id=R.W1.id, user_id=R.UG.id, session_id=s_id
    )
    # Then 1
    assert result.status == "cancelled"
    # Then 2
    assert warned(caplog, STG) is True


# =========================================================================== #
# promote_session
# =========================================================================== #


# [claude] MUSV-PM-01
def test_musv_pm_01__the_phones_file_becomes_a_ready_attachment_all_committed_together(
    db, R
):
    """MUSV-PM-01 — the phone's file becomes a ready attachment; all committed together.
    Rules: promote_session R2, TC1."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    result = svc.promote_session(
        db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ
    )
    # Then 1
    assert type(result).__name__ == "AttachmentResponse"
    # Then 2
    assert result.public_id == DEST(R)
    assert result.upload_status == "ready"
    assert result.file_name == "photo.jpg"
    assert result.note == "Front"
    # Then 3
    assert [(lk.entity_type.value, lk.entity_id) for lk in result.links] == [
        ("project", R.P1.id)
    ]
    # Then 4
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.status == "consumed"
    assert row.public_id is None
    # Then 5
    a = att_by_pid(db, DEST(R))
    assert a.workspace_id == R.W1.id
    assert a.upload_status == "ready"
    assert a.uploaded_by == R.UG.id
    assert a.version == 1700000001


# [claude] MUSV-PM-02
def test_musv_pm_02__ledger_rows_and_the_projects_activity_entry_are_committed_with_the_caller(
    db, R
):
    """MUSV-PM-02 — ledger rows and the project's activity entry are committed with the caller.
    Rules: promote_session R2, TC1; PR-5 (caller passed down)."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    result = svc.promote_session(
        db, workspace=R.W1, user=R.UG, session_id=s.id, payload=PRQ
    )
    # Then 1
    assert result.public_id == DEST(R)
    # Then 2
    db.rollback()
    assert ledger_types(db, DEST(R)) == ["pending", "ready"]
    # Then 3
    assert all(r.performed_by == R.UG.id for r in ledger_rows(db, DEST(R)))
    # Then 4
    n = count(
        db,
        "project_events",
        "project_id = :p AND event_type = 'attachment_added' AND performed_by = :u AND description = 'Attached photo.jpg'",
        p=R.P1.id,
        u=R.UG.id,
    )
    assert n == 1


# [claude] MUSV-PM-03
def test_musv_pm_03__the_file_is_moved_from_the_staging_id_to_the_servers_new_id(
    db, R, CL
):
    """MUSV-PM-03 — the file is moved from the staging id to the server's new id.
    Rules: promote_session R2 (manager R7)."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    result = svc.promote_session(
        db, workspace=R.W1, user=R.UG, session_id=s.id, payload=PRQ
    )
    # Then 1
    assert result.public_id == DEST(R)
    # Then 2
    assert CL.rr.call_count == 1
    assert kw(CL.rr)["from_public_id"] == STG
    assert kw(CL.rr)["to_public_id"] == DEST(R)
    # Then 3
    assert kw(CL.rr)["resource_type"] == "image"
    assert kw(CL.rr)["delivery_type"] == "authenticated"
    # Then 4
    assert CL.agr.call_count == 1
    assert kw(CL.agr)["public_id"] == DEST(R)


# [claude] MUSV-PM-04
def test_musv_pm_04__a_session_with_no_file_yet_is_refused_before_any_move(db, R, CL):
    """MUSV-PM-04 — a session with no file yet is refused before any move; nothing written.
    Rules: promote_session R3."""
    s = sess(db, R, "staged")
    commit_point(db)
    before_s = snap(db, s)
    before = counts(db)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == "No file is ready on this session."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl_called(CL) == []
    # Then 7
    assert x_count(db, x_id) == 0


# [claude] MUSV-PM-05
def test_musv_pm_05__an_oversized_staged_file_is_refused_before_any_move(db, R, CL):
    """MUSV-PM-05 — an oversized staged file is refused before any move.
    Rules: promote_session R3."""
    s = sess(db, R, "uploaded", file_size=10485761)
    commit_point(db)
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == TOO(10485761)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before
    # Then 6
    assert CL.rr.called is False


# [claude] MUSV-PM-06
def test_musv_pm_06__an_unknown_session_id_rolls_back_and_discards_pending_changes(
    db, R
):
    """MUSV-PM-06 — an unknown session id rolls back and discards pending changes.
    Rules: promote_session R1, TC3."""
    commit_point(db)
    before = counts(db)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=MISSING, payload=PRQ
        )
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert sp.rb.call_count >= 1
    assert sp.cm.called is False
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# [claude] MUSV-PM-07
def test_musv_pm_07__another_members_session_is_not_found_and_not_moved(db, R, CL):
    """MUSV-PM-07 — another member's session is not found and not moved.
    Rules: promote_session R1."""
    s = sess(db, R, "uploaded", created_by=R.U1.id)
    commit_point(db)
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert cl_called(CL) == []


# [claude] MUSV-PM-08
def test_musv_pm_08__a_failed_check_of_the_moved_file_reaches_the_caller_as_the_confirm_error(
    db, R, CL
):
    """MUSV-PM-08 — a failed check of the moved file reaches the caller as the confirm error.
    Rules: promote_session R4 (part that holds today)."""
    s = sess(db, R, "uploaded")
    CL.agr.side_effect = RuntimeError("boom")
    commit_point(db)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.promote_session(db, workspace=R.W1, user=R.UG, session_id=s.id, payload=PRQ)
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert CL.rr.call_count == 1
    assert CL.agr.call_count == 1


# [claude] MUSV-PM-09
@XF2204
def test_musv_pm_09__after_a_failed_check_the_moved_files_pointer_and_the_failed_attachment_are_committed(
    db, R, CL
):
    """MUSV-PM-09 — after a failed check, the moved file's pointer and the failed attachment are committed.
    Rules: promote_session R4 [BUG-2204]; HR-13."""
    s = sess(db, R, "uploaded")
    CL.agr.side_effect = RuntimeError("boom")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(AttachmentConfirmError):
        svc.promote_session(db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ)
    # Then 2
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id == DEST(R)
    assert row.status == "uploaded"
    # Then 3
    a = att_by_pid(db, DEST(R))
    assert a.upload_status == "failed"
    assert a.uploaded_by == R.UG.id
    # Then 4
    assert ledger_types(db, DEST(R)) == ["pending", "failed"]
    # Then 5
    assert (
        count(
            db,
            "attachment_links",
            "entity_type = 'project' AND entity_id = :p",
            p=R.P1.id,
        )
        == 1
    )


# [claude] MUSV-PM-10
@XF2204
def test_musv_pm_10__when_the_commit_of_that_failure_record_fails_the_commits_error_reaches_the_caller(
    db, R, CL
):
    """MUSV-PM-10 — when the commit of that failure record fails, the commit's error reaches the caller.
    Rules: promote_session R4 [BUG-2204], TC4."""
    s = sess(db, R, "uploaded")
    CL.agr.side_effect = RuntimeError("lookup")
    commit_point(db)
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 4
    assert counts(db) == before


# [claude] MUSV-PM-11
def test_musv_pm_11__a_failed_move_writes_nothing_and_keeps_the_session(db, R, CL):
    """MUSV-PM-11 — a failed move writes nothing and keeps the session.
    Rules: promote_session R4 (failed move)."""
    s = sess(db, R, "uploaded")
    CL.rr.side_effect = RuntimeError("down")
    commit_point(db)
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == "Cloudinary move failed: down"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before


# [claude] MUSV-PM-12
def test_musv_pm_12__a_full_record_rolls_back_no_attachment_session_unchanged(db, R):
    """MUSV-PM-12 — a full record rolls back: no attachment, session unchanged.
    Rules: promote_session R5, TC3."""
    full(db, R, R.P1)
    s = sess(db, R, "uploaded")
    commit_point(db)
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before


# [claude] MUSV-PM-13
def test_musv_pm_13__a_failing_commit_after_a_good_promote_keeps_the_session_uploaded(
    db, R
):
    """MUSV-PM-13 — a failing commit after a good promote keeps the session uploaded.
    Rules: promote_session R5, TC4."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    before = counts(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.promote_session(db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ)
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    row = reread(db, MobileUploadSession, s_id)
    assert row.status == "uploaded"
    assert row.public_id == STG
    # Then 4
    assert counts(db) == before


# [claude] MUSV-PM-14
@XF2139
def test_musv_pm_14__promotes_first_read_of_the_session_is_locked_before_anything_acts(
    db, R, CL
):
    """MUSV-PM-14 — promote's first read of the session is locked, before anything acts.
    Rules: promote_session R1 [BUG-2139]; HR-10."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    s_id = s.id
    with event_log(db, CL) as ev:
        result = svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ
        )
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert "FOR UPDATE" in ev[first_read(ev)][1].upper()
    # Then 3
    assert acted_before(ev, first_read(ev)) is False


# [claude] MUSV-PM-15
@XF2134
def test_musv_pm_15__a_private_project_the_caller_may_not_open_is_refused_before_the_move(
    db, R, CL
):
    """MUSV-PM-15 — a private project the caller may not open is refused before the move.
    Rules: promote_session R2, R3 [BUG-2134]; PR-2, PR-5."""
    p2 = proj(db, R, "Bridge", private=True)
    s = sess(db, R, "uploaded", entity_id=p2.id, entity_label="Bridge")
    commit_point(db)
    p2_id = p2.id
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before
    # Then 6
    assert CL.rr.called is False


# [claude] MUSV-PM-16
@XF2134
def test_musv_pm_16__membership_of_another_private_project_does_not_open_this_one(
    db, R
):
    """MUSV-PM-16 — membership of another private project does not open this one.
    Rules: promote_session R3 [BUG-2134]; PR-2 (grant held on a different record)."""
    p2 = proj(db, R, "Bridge", private=True)
    p3 = proj(db, R, "Canal", private=True)
    pmem(db, R, p3, R.UG)
    s = sess(db, R, "uploaded", entity_id=p2.id, entity_label="Bridge")
    commit_point(db)
    p2_id = p2.id
    before_s = snap(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert counts(db) == before


# [claude] MUSV-PM-17
@XF2134
def test_musv_pm_17__a_project_deleted_after_the_session_opened_is_refused_before_the_move(
    db, R, CL
):
    """MUSV-PM-17 — a project deleted after the session opened is refused before the move.
    Rules: promote_session R3 [BUG-2134]; PR-1."""
    p2 = proj(db, R, "Bridge", deleted=True)
    s = sess(db, R, "uploaded", entity_id=p2.id, entity_label="Bridge")
    commit_point(db)
    p2_id = p2.id
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.promote_session(
            db, workspace=R.W1, user=R.UG, session_id=before_s["id"], payload=PRQ
        )
    # Then 2
    assert str(exc.value) == NF("project", p2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert CL.rr.called is False


# [claude] MUSV-PM-18
def test_musv_pm_18__a_project_member_attaches_to_the_private_project(db, R):
    """MUSV-PM-18 — a project member attaches to the private project.
    Rules: promote_session R2; PR-2, PR-5."""
    p2 = proj(db, R, "Bridge", private=True)
    pmem(db, R, p2, R.UG)
    s = sess(db, R, "uploaded", entity_id=p2.id, entity_label="Bridge")
    commit_point(db)
    s_id = s.id
    result = svc.promote_session(
        db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ
    )
    # Then 1
    assert result.upload_status == "ready"
    assert result.public_id == DEST(R)
    # Then 2
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "consumed"


# [claude] MUSV-PM-19
@XF2204
def test_musv_pm_19__the_hr13_commit_after_a_failed_check_also_commits_an_unrelated_pending_row(
    db, R, CL
):
    """MUSV-PM-19 — the HR-13 commit after a failed check also commits an unrelated pending row.
    Rules: promote_session R4a [BUG-2204]; HR-13."""
    s = sess(db, R, "uploaded")
    CL.agr.side_effect = RuntimeError("boom")
    commit_point(db)
    s_id = s.id
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.promote_session(db, workspace=R.W1, user=R.UG, session_id=s_id, payload=PRQ)
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    db.rollback()
    assert x_count(db, x_id) == 1
    # Then 5
    assert reread(db, MobileUploadSession, s_id).public_id == DEST(R)


# =========================================================================== #
# get_public_session
# =========================================================================== #


# [claude] MUSV-GP-01
def test_musv_gp_01__a_w2_session_is_found_by_its_token_and_answered_with_three_fields_only(
    db, R
):
    """MUSV-GP-01 — a W2 session is found by its token and answered with three fields only.
    Rules: get_public_session R1."""
    sess(db, R, where="W2")
    commit_point(db)
    result = svc.get_public_session(db, raw_token=RAW2)
    # Then 1
    assert type(result).__name__ == "MobileUploadPublicSessionResponse"
    # Then 2
    assert set(result.model_dump()) == {"status", "entity_label", "expires_at"}
    # Then 3
    assert result.status == "waiting"
    assert result.entity_label == "Tender"


# [claude] MUSV-GP-02
def test_musv_gp_02__an_unknown_token_is_not_found(db, R):
    """MUSV-GP-02 — an unknown token is not found.
    Rules: get_public_session R2."""
    sess(db, R)
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_public_session(db, raw_token=RAWX)
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GP-03
def test_musv_gp_03__a_consumed_session_is_no_longer_available(db, R):
    """MUSV-GP-03 — a consumed session is no longer available.
    Rules: get_public_session R2."""
    sess(db, R, status="consumed")
    commit_point(db)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.get_public_session(db, raw_token=RAW1)
    # Then 2
    assert str(exc.value) == GONE
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] MUSV-GP-04
def test_musv_gp_04__an_expired_session_expired_in_memory_only(db, R):
    """MUSV-GP-04 — an expired session: "expired" in memory only, nothing rolled back or saved.
    Rules: get_public_session R2 (D6), TC6."""
    s = sess(db, R, expires_at=PAST)
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.get_public_session(db, raw_token=RAW1)
    # Then 2
    assert str(exc.value) == EXPD
    # Then 3
    assert sp.cm.called is False
    assert sp.rb.called is False
    # Then 4
    assert s in db.dirty
    # Then 5
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).status == "waiting"


# [claude] MUSV-GP-05
def test_musv_gp_05__a_public_read_neither_commits_nor_rolls_back_pending_changes_stay(
    db, R
):
    """MUSV-GP-05 — a public read neither commits nor rolls back; pending changes stay.
    Rules: get_public_session R2, TC6."""
    sess(db, R)
    commit_point(db)
    R.F9.name = "Factory Edited"
    with spies(db) as sp:
        result = svc.get_public_session(db, raw_token=RAW1)
    # Then 1
    assert result.status == "waiting"
    # Then 2
    assert sp.cm.called is False
    assert sp.rb.called is False
    # Then 3
    assert R.F9 in db.dirty
    assert len(db.dirty) == 1


# =========================================================================== #
# public_sign
# =========================================================================== #


# [claude] MUSV-PS-01
def test_musv_ps_01__a_w2_session_is_signed_in_its_own_workspace_and_committed(db, R):
    """MUSV-PS-01 — a W2 session is signed in its own workspace and committed.
    Rules: public_sign R1, R2, TC1."""
    s = sess(db, R, where="W2")
    commit_point(db)
    s_id = s.id
    w2_id, w2_name = R.W2.id, R.W2.name
    result = svc.public_sign(db, payload=SRQ(RAW2))
    # Then 1
    assert type(result).__name__ == "MobileUploadPublicSignResponse"
    # Then 2
    assert (
        result.public_id
        == "development/ws-" + str(w2_id) + "/mobile-staging/" + str(s_id) + "/" + TOKEN
    )
    # Then 3
    assert result.asset_folder == "Dev/" + w2_name + "/Mobile Staging/session-" + str(
        s_id
    )
    # Then 4
    assert result.signature == "sig-x"
    assert result.timestamp == 1767225600
    # Then 5
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id == result.public_id
    assert row.file_name == "scan.jpg"
    assert row.mime_type == "image/jpeg"
    assert row.file_size == 3000
    assert row.resource_type == "image"
    assert row.status == "waiting"


# [claude] MUSV-PS-02
def test_musv_ps_02__a_second_sign_deletes_the_earlier_staged_file(db, R, CL):
    """MUSV-PS-02 — a second sign deletes the earlier staged file.
    Rules: public_sign R2, R3 (part that holds today and after)."""
    s = sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    commit_point(db)
    s_id = s.id
    result = svc.public_sign(db, payload=SRQ(RAW1))
    # Then 1
    assert result.public_id != OLD
    # Then 2
    assert CL.dr.call_count == 1
    assert kw(CL.dr)["public_id"] == OLD
    # Then 3
    db.rollback()
    assert reread(db, MobileUploadSession, s_id).public_id == result.public_id


# [claude] MUSV-PS-03
def test_musv_ps_03__a_failure_after_the_flush_keeps_the_sessions_earlier_file_pointer(
    db, R, CL
):
    """MUSV-PS-03 — a failure after the flush keeps the session's earlier file pointer.
    Rules: public_sign R3, R4, TC3."""
    CL.setting("CLOUDINARY_CLOUD_NAME", "")
    s = sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        svc.public_sign(db, payload=SRQ(RAW1))
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id == OLD
    assert row.asset_folder == "Dev/x/old"
    assert row.file_name is None


# [claude] MUSV-PS-04
@XF2205
def test_musv_ps_04__a_failed_sign_never_deletes_the_earlier_staged_file(db, R, CL):
    """MUSV-PS-04 — a failed sign never deletes the earlier staged file.
    Rules: public_sign R3 [BUG-2205]."""
    CL.setting("CLOUDINARY_CLOUD_NAME", "")
    s = sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError):
        svc.public_sign(db, payload=SRQ(RAW1))
    # Then 2
    assert reread(db, MobileUploadSession, s_id).public_id == OLD
    # Then 3
    assert CL.dr.called is False


# [claude] MUSV-PS-05
@XF2205
def test_musv_ps_05__on_success_the_commit_comes_before_the_earlier_files_delete(
    db, R, CL
):
    """MUSV-PS-05 — on success the commit comes before the earlier file's delete.
    Rules: public_sign R3 [BUG-2205]."""
    sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    commit_point(db)
    with order_log(db, CL) as order:
        result = svc.public_sign(db, payload=SRQ(RAW1))
    # Then 1
    assert result.public_id != OLD
    # Then 2
    assert order.count("dr") == 1
    assert "commit" in order
    # Then 3
    assert order.index("commit") < order.index("dr")


# [claude] MUSV-PS-06
def test_musv_ps_06__an_unknown_token_rolls_back_and_discards_pending_changes(db, R):
    """MUSV-PS-06 — an unknown token rolls back and discards pending changes.
    Rules: public_sign R1, R4, TC3."""
    s = sess(db, R)
    commit_point(db)
    before_s = snap(db, s)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc, spies(db) as sp:
        svc.public_sign(db, payload=SRQ(RAWX))
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert sp.rb.call_count >= 1
    assert sp.cm.called is False
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, MobileUploadSession, before_s)


# [claude] MUSV-PS-07
def test_musv_ps_07__a_session_that_already_has_a_file_is_refused_nothing_changed(
    db, R, CL
):
    """MUSV-PS-07 — a session that already has a file is refused; nothing changed.
    Rules: public_sign R2, R4."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    before_s = snap(db, s)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        svc.public_sign(db, payload=SRQ(RAW1))
    # Then 2
    assert str(exc.value) == HASF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert x_count(db, x_id) == 0


# [claude] MUSV-PS-08
def test_musv_ps_08__a_failing_commit_saves_none_of_the_new_staging_columns(db, R):
    """MUSV-PS-08 — a failing commit saves none of the new staging columns.
    Rules: public_sign R4, TC4."""
    s = sess(db, R)
    commit_point(db)
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.public_sign(db, payload=SRQ(RAW1))
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    assert unchanged(db, MobileUploadSession, before_s)


# [claude] MUSV-PS-09
@XF2205
def test_musv_ps_09__a_resign_whose_commit_fails_never_deletes_the_earlier_file(
    db, R, CL
):
    """MUSV-PS-09 — a re-sign whose commit fails never deletes the earlier file.
    Rules: public_sign R3 [BUG-2205], R4, TC4."""
    s = sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.public_sign(db, payload=SRQ(RAW1))
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id == OLD
    assert row.asset_folder == "Dev/x/old"
    # Then 4
    assert CL.dr.called is False


# [claude] MUSV-PS-10
def test_musv_ps_10__a_raising_delete_of_the_earlier_file_after_the_commit_is_swallowed(
    db, R, CL
):
    """MUSV-PS-10 — a raising delete of the earlier file after the commit is swallowed; the sign is saved and answered.
    Rules: public_sign R3a [BUG-2205] (part that holds today)."""
    s = sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    CL.dr.side_effect = RuntimeError("down")
    commit_point(db)
    s_id = s.id
    result = svc.public_sign(db, payload=SRQ(RAW1))
    # Then 1
    assert result.public_id != OLD
    assert result.signature == "sig-x"
    # Then 2
    assert CL.dr.call_count == 1
    # Then 3
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id == result.public_id
    assert row.file_name == "scan.jpg"


# [claude] MUSV-PS-11
@XF2136
def test_musv_ps_11__that_delete_error_is_logged_as_a_warning_naming_the_earlier_file(
    db, R, CL, caplog
):
    """MUSV-PS-11 — that delete error is logged as a WARNING naming the earlier file.
    Rules: public_sign R3a [BUG-2205] with manager _destroy_staging_asset R3 [BUG-2136]."""
    sess(db, R, public_id=OLD, asset_folder="Dev/x/old")
    CL.dr.side_effect = RuntimeError("down")
    caplog.set_level(logging.WARNING)
    commit_point(db)
    result = svc.public_sign(db, payload=SRQ(RAW1))
    # Then 1
    assert result.public_id != OLD
    # Then 2
    assert warned(caplog, OLD) is True


# =========================================================================== #
# public_confirm
# =========================================================================== #


# [claude] MUSV-PC-01
def test_musv_pc_01__a_verified_file_makes_the_session_uploaded_committed(db, R, CL):
    """MUSV-PC-01 — a verified file makes the session uploaded, committed.
    Rules: public_confirm R1, R2, TC1."""
    s = sess(db, R, "staged")
    commit_point(db)
    s_id = s.id
    result = svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 1
    assert type(result).__name__ == "MobileUploadPublicSessionResponse"
    assert result.status == "uploaded"
    # Then 2
    assert CL.gr.call_count == 1
    assert kw(CL.gr)["public_id"] == STG
    # Then 3
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.status == "uploaded"
    assert row.format == "jpg"
    assert row.version == 1700000000
    assert row.file_size == 2048


# [claude] MUSV-PC-02
def test_musv_pc_02__an_oversized_phone_file_reaches_the_caller_as_the_confirm_error(
    db, R, CL
):
    """MUSV-PC-02 — an oversized phone file reaches the caller as the confirm error.
    Rules: public_confirm R3 (part that holds today)."""
    sess(db, R, "staged")
    CL.gr.return_value = {**GR, "bytes": 10485761}
    commit_point(db)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 2
    assert str(exc.value) == TOO(10485761)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert CL.dr.call_count == 1
    assert kw(CL.dr)["public_id"] == STG


# [claude] MUSV-PC-03
@XF2137
def test_musv_pc_03__the_cleared_session_of_an_oversized_file_is_committed_then_the_error_returned(
    db, R, CL
):
    """MUSV-PC-03 — the cleared session of an oversized file is committed, then the error returned.
    Rules: public_confirm R3 [BUG-2137]; HR-13."""
    s = sess(db, R, "staged")
    CL.gr.return_value = {**GR, "bytes": 10485761}
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(AttachmentConfirmError):
        svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 2
    db.rollback()
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id is None
    assert row.asset_folder is None
    # Then 3
    assert reread(db, MobileUploadSession, s_id).status == "waiting"


# [claude] MUSV-PC-04
@XF2137
def test_musv_pc_04__when_the_commit_of_the_cleared_session_fails_the_commits_error_reaches_the_caller(
    db, R, CL
):
    """MUSV-PC-04 — when the commit of the cleared session fails, the commit's error reaches the caller.
    Rules: public_confirm R3 [BUG-2137], TC4."""
    s = sess(db, R, "staged")
    CL.gr.return_value = {**GR, "bytes": 10485761}
    commit_point(db)
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.public_confirm(db, payload=CFQ(RAW1))
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    assert unchanged(db, MobileUploadSession, before_s)


# [claude] MUSV-PC-05
def test_musv_pc_05__a_failed_lookup_changes_nothing_nothing_saved(db, R, CL):
    """MUSV-PC-05 — a failed lookup changes nothing; nothing saved.
    Rules: public_confirm R3 (other refusals)."""
    s = sess(db, R, "staged")
    CL.gr.side_effect = RuntimeError("boom")
    commit_point(db)
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 5
    assert CL.dr.called is False


# [claude] MUSV-PC-06
def test_musv_pc_06__an_already_uploaded_session_is_refused_rolled_back_pending_changes_discarded(
    db, R, CL
):
    """MUSV-PC-06 — an already uploaded session is refused, rolled back, pending changes discarded.
    Rules: public_confirm R4, TC3."""
    s = sess(db, R, "uploaded")
    commit_point(db)
    before_s = snap(db, s)
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc, spies(db) as sp:
        svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 2
    assert str(exc.value) == HASF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert sp.rb.call_count >= 1
    assert sp.cm.called is False
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert unchanged(db, MobileUploadSession, before_s)
    # Then 7
    assert CL.gr.called is False


# [claude] MUSV-PC-07
def test_musv_pc_07__an_unknown_token_is_not_found(db, R):
    """MUSV-PC-07 — an unknown token is not found.
    Rules: public_confirm R1, R4."""
    s = sess(db, R, "staged")
    commit_point(db)
    before_s = snap(db, s)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        svc.public_confirm(db, payload=CFQ(RAWX))
    # Then 2
    assert str(exc.value) == NOTF
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert unchanged(db, MobileUploadSession, before_s)


# [claude] MUSV-PC-08
def test_musv_pc_08__a_failing_commit_after_a_good_confirm_keeps_the_session_waiting(
    db, R
):
    """MUSV-PC-08 — a failing commit after a good confirm keeps the session waiting.
    Rules: public_confirm R2, TC4."""
    s = sess(db, R, "staged")
    commit_point(db)
    s_id = s.id
    # Then 1
    with pytest.raises(RuntimeError) as exc, failing_commit(db) as fc:
        svc.public_confirm(db, payload=CFQ(RAW1))
    assert str(exc.value) == "boom"
    # Then 2
    assert fc.rb.call_count >= 1
    # Then 3
    row = reread(db, MobileUploadSession, s_id)
    assert row.status == "waiting"
    assert row.format is None


# [claude] MUSV-PC-09
@XF2137
def test_musv_pc_09__the_cleared_sessions_commit_also_commits_an_unrelated_pending_row(
    db, R, CL
):
    """MUSV-PC-09 — the cleared session's commit also commits an unrelated pending row.
    Rules: public_confirm R3a [BUG-2137]; HR-13."""
    s = sess(db, R, "staged")
    CL.gr.return_value = {**GR, "bytes": 10485761}
    commit_point(db)
    s_id = s.id
    x_id = pending_x(db, R)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.public_confirm(db, payload=CFQ(RAW1))
    # Then 2
    assert str(exc.value) == TOO(10485761)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    db.rollback()
    assert x_count(db, x_id) == 1
    # Then 5
    row = reread(db, MobileUploadSession, s_id)
    assert row.public_id is None
    assert row.status == "waiting"
