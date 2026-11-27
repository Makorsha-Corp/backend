"""Unit tests for app/managers/mobile_upload_session_manager.py.

Implements tests/unit/managers/mobile_upload_session_manager.cases.md (revision 4),
one test per card, in card order. Real Postgres session (`db` fixture), rolled
back after each test.

Externals patched in every test (fixture `CL`, Conventions "Settings and time"
and "Cloudinary"): the settings on `app.core.config.settings`; `utcnow` of this
module and of `app.dao.mobile_upload_session`; `uuid.uuid4`, `time.time` and
`secrets.token_urlsafe` through this module; the six Cloudinary functions as
imported in this module and the four as imported in
`app.managers.attachment_manager` (AttachmentManager itself is real). Nothing
touches the network. `CL.real("uuid")` / `CL.real("raw")` / `CL.real("gus")`
undo one patch for the cards that say "real uuid" / "real raw" / "real gus".

The Standing rows are fixture `R` (`R.W1`, `R.UG`, `R.MG`, `R.P1` ...): the
cards' own `S` is the session row of each card. Given rows are built by the
helpers below, one flush per row. `# Then N` marks the checks of Then line N.
"""
import hashlib
import inspect
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event, text
from sqlalchemy import inspect as sa_inspect

from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.core.config import settings
from app.core.security import hash_refresh_token
from app.managers.attachment_manager import (
    AttachmentLimitError,
    AttachmentNotFoundError,
    attachment_manager,
)
from app.managers.mobile_upload_session_manager import (
    MobileUploadSessionError,
    MobileUploadSessionNotFoundError,
    _naive_utc,
    mobile_upload_session_manager,
)
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink
from app.models.enums import AttachmentEntityTypeEnum as ET
from app.models.enums import MobileUploadSessionStatusEnum
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.machine import Machine
from app.models.mobile_upload_session import MobileUploadSession
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_member import ProjectMember
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.attachment import AttachmentSignRequest
from app.utils.attachment_allowlist import (
    AttachmentConfirmError,
    AttachmentValidationError,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = mobile_upload_session_manager"
M = mobile_upload_session_manager
MOD = "app.managers.mobile_upload_session_manager"
AMOD = "app.managers.attachment_manager"
LOGGER_NAME = MOD

MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)  # noqa: DTZ001  (Conventions: naive)
NOW_UTC = NOW.replace(tzinfo=timezone.utc)
PAST = NOW_UTC - timedelta(days=1)
LATER = NOW_UTC + timedelta(days=1)
US = timedelta(microseconds=1)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
P6 = timezone(timedelta(hours=6))
M5 = timezone(timedelta(hours=-5))
RAW1 = "raw-token-1"
RAW0 = "raw-token-0"
RAW2 = "raw-token-2"
RAWT = "fixed-raw-token"
TOKEN = "0123456789abcdef0123456789abcdef"
STG = "development/ws-0/mobile-staging/0/" + "f" * 32
OLD = "development/ws-0/mobile-staging/0/" + "e" * 32
MAXB = 10485760
GR = {"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000000}
GRA = {
    "resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000001,
    "secure_url": "https://res.example/a.jpg", "width": 800, "height": 600,
    "asset_id": "a" * 32, "etag": "e" * 32,
}
SETTINGS = {
    "CLOUDINARY_UPLOAD_ENV": "development",
    "ENVIRONMENT": "development",
    "CLOUDINARY_CLOUD_NAME": "demo-cloud",
    "CLOUDINARY_API_KEY": "123456",
    "CLOUDINARY_API_SECRET": "s3cret",
    "MAX_ATTACHMENTS_PER_ENTITY": 25,
}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# Convention "XID(k)"
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


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
    patchers = {}

    def start(key, target, **kwargs):
        p = patch(target, **kwargs)
        setattr(ns, key, p.start())
        patchers[key] = p

    start("clock", MOD + ".utcnow", return_value=NOW)
    start("dao_clock", "app.dao.mobile_upload_session.utcnow", return_value=NOW)
    start("uuid", MOD + ".uuid.uuid4", return_value=uuid.UUID(TOKEN))
    start("time", MOD + ".time.time", return_value=1767225600.9)
    start("raw", MOD + ".secrets.token_urlsafe", return_value=RAWT)
    start("gus", MOD + ".generate_upload_signature", autospec=True, return_value="sig-x")
    start("gr", MOD + ".get_resource", autospec=True, return_value=dict(GR))
    start("dr", MOD + ".destroy_resource", autospec=True, return_value={"result": "ok"})
    start("rr", MOD + ".rename_resource", autospec=True, return_value={})
    start("um", MOD + ".update_resource_metadata", autospec=True, return_value={"result": "ok"})
    start("bsdu", MOD + ".build_signed_delivery_url", autospec=True, return_value="https://signed.example/preview")
    start("agr", AMOD + ".get_resource", autospec=True, return_value=dict(GRA))
    start("adr", AMOD + ".destroy_resource", autospec=True, return_value={"result": "ok"})
    start("ags", AMOD + ".generate_upload_signature", autospec=True, return_value="sig-a")
    start("absdu", AMOD + ".build_signed_delivery_url", autospec=True, return_value="https://signed.example/a")

    def setting(name, value):
        monkeypatch.setattr(settings, name, value)

    def real(key):
        patchers.pop(key).stop()

    ns.setting = setting
    ns.real = real
    yield ns
    for p in patchers.values():
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
def member(db, R, u, role, status="active", ws=None, **over):
    ws = ws or R.W1
    return add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status, **over))


@pytest.fixture
def R(db):
    """Standing rows: W0, W1, W2; U1, U2, UG with W1 memberships (MG = UG's); F0, F1, F9; WT1; P1."""
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
    r.F0 = add(db, Factory(workspace_id=r.W0.id, name="Factory Zero", abbreviation="F0"))
    r.F1 = add(db, Factory(workspace_id=r.W1.id, name="Factory One", abbreviation="F1"))
    r.F9 = add(db, Factory(workspace_id=r.W2.id, name="Factory Nine", abbreviation="F9"))
    r.WT1 = add(db, WorkOrderType(workspace_id=r.W1.id, name="Repair"))
    r.P1 = proj(db, r, "Tender")
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def mg_but(db, R, **over):
    """"UG's W1 membership but X": changes MG and flushes."""
    for k, v in over.items():
        setattr(R.MG, k, v)
    db.flush()


# "removed" = status "inactive", left_at T0
REMOVED = {"status": "inactive", "left_at": T0}


def drop_mg(db, R):
    """"`db.delete(MG)`, flush"."""
    db.delete(R.MG)
    db.flush()


def set_owner(db, ws, u):
    ws.owner_user_id = u.id
    db.flush()


def proj(db, R, name, where="W1", private=False, deleted=False, **over):
    """proj / W0 proj / W2 proj; `private`, `deleted` as Conventions; `over` = the columns after "but"."""
    ws = getattr(R, where)
    factory = {"W0": R.F0, "W1": R.F1, "W2": R.F9}[where]
    fields = {
        "workspace_id": ws.id, "factory_id": factory.id, "name": name,
        "description": "Main", "created_by": R.U1.id,
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=R.U1.id)
    fields.update(over)
    return add(db, Project(**fields))


def pmem(db, R, p, u):
    return add(db, ProjectMember(workspace_id=p.workspace_id, project_id=p.id, user_id=u.id, assigned_by=R.U1.id))


def comp(db, p, name):
    return add(db, ProjectComponent(workspace_id=p.workspace_id, project_id=p.id, name=name))


def machine(db, R, name, deleted=False, **over):
    fields = {"workspace_id": R.W1.id, "factory_id": R.F1.id, "name": name}
    if deleted:
        fields.update(is_active=False, is_deleted=True, deleted_at=T0, deleted_by=R.U1.id)
    fields.update(over)
    return add(db, Machine(**fields))


def wo(db, R, number, deleted=False):
    fields = {
        "workspace_id": R.W1.id, "work_order_number": number, "title": "Fix press",
        "factory_id": R.F1.id, "work_order_type_id": R.WT1.id,
    }
    if deleted:
        fields["is_deleted"] = True
    return add(db, WorkOrder(**fields))


def po(db, R, number, **over):
    """po "N": first ST (a Status of the po's workspace), then the purchase order."""
    ws_id = over.get("workspace_id", R.W1.id)
    st = add(db, Status(workspace_id=ws_id, name="Draft", comment="Stage"))
    fields = {
        "workspace_id": R.W1.id, "po_number": number, "destination_type": "storage",
        "destination_id": MISSING, "subtotal": 0, "total_amount": 0,
        "current_status_id": st.id, "created_by": R.U1.id,
    }
    fields.update(over)
    return add(db, PurchaseOrder(**fields))


def ticket(db, R, number, **over):
    fields = {
        "workspace_id": R.W1.id, "ticket_number": number, "title": "Printer jam",
        "description": "It jams", "created_by": R.U1.id,
    }
    fields.update(over)
    return add(db, HelpTicket(**fields))


def sess(R, kind="sess", **over):
    """sess / staged / uploaded, unsaved; `over` = the columns after "but". Save with add(db, ...)."""
    fields = {
        "workspace_id": R.W1.id, "created_by": R.UG.id, "entity_type": "project",
        "entity_id": R.P1.id, "entity_label": "Tender", "token_hash": H(RAW1),
        "expires_at": LATER, "status": "waiting",
    }
    if kind in ("staged", "uploaded"):
        fields.update(
            public_id=STG, asset_folder="Dev/x/Mobile Staging/session-0", resource_type="image",
            file_name="photo.jpg", mime_type="image/jpeg", file_size=2048,
        )
    if kind == "uploaded":
        fields.update(status="uploaded", format="jpg", version=1700000000)
    fields.update(over)
    return MobileUploadSession(**fields)


def full(db, R, p):
    """full(P): 25 ready attachments, each linked to project P."""
    for i in range(1, 26):
        a = add(db, Attachment(
            workspace_id=R.W1.id, file_name=f"f{i}.jpg", mime_type="image/jpeg", file_size=1,
            uploaded_by=R.U1.id, upload_status="ready", public_id=f"full/{i}",
        ))
        add(db, AttachmentLink(
            workspace_id=R.W1.id, attachment_id=a.id, entity_type="project", entity_id=p.id, linked_by=R.U1.id,
        ))


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #

def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def snap(db, row):
    """Snapshot for unchanged(X), taken after the last Given line."""
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def unchanged(db, row, before):
    db.expire_all()
    fresh = db.get(type(row), before["id"])
    return fresh is not None and {k: getattr(fresh, k) for k in _columns(type(row))} == before


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def counts(db):
    """"nothing written": row counts of the five tables (all workspaces)."""
    return tuple(
        db.scalar(text(f"SELECT count(*) FROM {t}"))
        for t in ("mobile_upload_sessions", "attachments", "attachment_links", "attachment_ledger", "project_events")
    )


def count(db, table, cond, **params):
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {cond}"), params)


def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


@pytest.fixture
def warnings_log(caplog):
    """Convention "warnings": set before the When; call the result after it."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    def warnings():
        return [r for r in caplog.records if r.levelno == logging.WARNING and r.name == LOGGER_NAME]

    return warnings


XF1282 = pytest.mark.xfail(strict=True, reason="BUG-1282: expires_at compared and written by clock time, not UTC moment")
XF2130 = pytest.mark.xfail(strict=True, reason="BUG-2130: QR session opened for a missing / deleted / other-workspace record")
XF2131 = pytest.mark.xfail(strict=True, reason="BUG-2131: QR session opened for a record the caller may not open")
XF2132 = pytest.mark.xfail(strict=True, reason="BUG-2132: looked-up label longer than 80 characters not cut")
XF2133 = pytest.mark.xfail(strict=True, reason="BUG-2133: file moved in Cloudinary before the attach is known to be allowed")
XF2134 = pytest.mark.xfail(strict=True, reason="BUG-2134: attach does not re-check the record (PR-1 / PR-2)")
XF2135 = pytest.mark.xfail(strict=True, reason="BUG-2135: promoted file name loses its extension")
XF2136 = pytest.mark.xfail(strict=True, reason="BUG-2136: swallowed Cloudinary error not logged")
XF2138 = pytest.mark.xfail(strict=True, reason="BUG-2138: cancel leaves a waiting session's staged file in Cloudinary")
XF2139 = pytest.mark.xfail(strict=True, reason="BUG-2139: promote / cancel read the session without a row lock")
XF2140 = pytest.mark.xfail(strict=True, reason="BUG-2140: re-sign deletes the earlier file before validating")
XF2141 = pytest.mark.xfail(strict=True, reason="BUG-2141: CloudinaryNotConfiguredError wrapped as AttachmentConfirmError")


# =========================================================================== #
# _naive_utc
# =========================================================================== #

def test_mobs_n_01__naive_value_unchanged():
    """MOBS-N-01 — a naive value comes back unchanged.
    Rules: _naive_utc R1."""
    result = _naive_utc(NOW)
    # Then 1
    assert result == datetime(2026, 3, 5, 12, 0, 0)  # noqa: DTZ001
    assert result.tzinfo is None


def test_mobs_n_02__utc_value_keeps_clock_time():
    """MOBS-N-02 — a UTC value keeps its clock time.
    Rules: _naive_utc R2."""
    result = _naive_utc(NOW_UTC)
    # Then 1
    assert result == datetime(2026, 3, 5, 12, 0, 0)  # noqa: DTZ001
    assert result.tzinfo is None


@XF1282
def test_mobs_n_03__plus_six_converted_to_utc():
    """MOBS-N-03 — a +06:00 value is converted to UTC.
    Rules: _naive_utc R2 [BUG-1282]."""
    result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=P6))
    # Then 1
    assert result.tzinfo is None
    # Then 2
    assert result == datetime(2025, 12, 31, 18, 0, 0)  # noqa: DTZ001


# =========================================================================== #
# _hash_token
# =========================================================================== #

def test_mobs_h_01__sha256_hex_as_refresh_hash():
    """MOBS-H-01 — the token's SHA-256 hex, as the refresh-token hash.
    Rules: _hash_token R1."""
    result = M._hash_token("Abc-123_x")
    # Then 1
    assert result == H("Abc-123_x")
    # Then 2
    assert result == hash_refresh_token("Abc-123_x")
    # Then 3
    assert len(result) == 64
    assert result == result.lower()


def test_mobs_h_02__empty_token_hashed():
    """MOBS-H-02 — the empty token is hashed too.
    Rules: _hash_token R1."""
    result = M._hash_token("")
    # Then 1
    assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# =========================================================================== #
# _upload_env / _is_production
# =========================================================================== #

def test_mobs_e_01__upload_env_wins(CL):
    """MOBS-E-01 — a non-empty upload environment wins over ENVIRONMENT.
    Rules: _upload_env R1."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "staging")
    CL.setting("ENVIRONMENT", "production")
    result = M._upload_env()
    # Then 1
    assert result == "staging"


def test_mobs_e_02__empty_upload_env_falls_back(CL):
    """MOBS-E-02 — an empty upload environment falls back to ENVIRONMENT.
    Rules: _upload_env R1."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "")
    CL.setting("ENVIRONMENT", "qa")
    result = M._upload_env()
    # Then 1
    assert result == "qa"


def test_mobs_e_03__production_exactly(CL):
    """MOBS-E-03 — "production" exactly is production.
    Rules: _is_production R2."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "production")
    result = M._is_production()
    # Then 1
    assert result is True


def test_mobs_e_04__capital_production_is_not(CL):
    """MOBS-E-04 — "Production" with a capital is not production.
    Rules: _is_production R2."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "Production")
    result = M._is_production()
    # Then 1
    assert result is False


def test_mobs_e_05__leading_space_production_is_not(CL):
    """MOBS-E-05 — " production" with a leading space is not production.
    Rules: _is_production R2."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", " production")
    result = M._is_production()
    # Then 1
    assert result is False


# =========================================================================== #
# build_staging_public_id
# =========================================================================== #

def test_mobs_pi_01__env_prefix_outside_production():
    """MOBS-PI-01 — outside production the id has the environment in front.
    Rules: build_staging_public_id R2."""
    result = M.build_staging_public_id(workspace_id=7, session_id=12)
    # Then 1
    assert result == "development/ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"


def test_mobs_pi_02__no_prefix_in_production(CL):
    """MOBS-PI-02 — in production the id has no prefix.
    Rules: build_staging_public_id R1."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "production")
    result = M.build_staging_public_id(workspace_id=7, session_id=12)
    # Then 1
    assert result == "ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"


def test_mobs_pi_03__env_from_environment(CL):
    """MOBS-PI-03 — the environment comes from ENVIRONMENT when the upload one is empty.
    Rules: build_staging_public_id R2, _upload_env R1."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "")
    CL.setting("ENVIRONMENT", "qa")
    result = M.build_staging_public_id(workspace_id=7, session_id=12)
    # Then 1
    assert result == "qa/ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"


def test_mobs_pi_04__new_hex_token_each_call(CL):
    """MOBS-PI-04 — each call gives a new 32-character lowercase hex token.
    Rules: build_staging_public_id R1."""
    CL.real("uuid")
    first = M.build_staging_public_id(workspace_id=7, session_id=12)
    result = M.build_staging_public_id(workspace_id=7, session_id=12)
    # Then 1
    assert result != first
    # Then 2
    assert re.fullmatch(r"development/ws-7/mobile-staging/12/[0-9a-f]{32}", result) is not None


# =========================================================================== #
# build_staging_asset_folder
# =========================================================================== #

def test_mobs_af_01__production_folder_name_as_given(CL):
    """MOBS-AF-01 — production folder, the name used as given.
    Rules: build_staging_asset_folder R1."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "production")
    result = M.build_staging_asset_folder(workspace_name=" Acme/East ", session_id=12)
    # Then 1
    assert result == " Acme/East /Mobile Staging/session-12"


def test_mobs_af_02__other_env_gets_dev(CL):
    """MOBS-AF-02 — any other environment gets "Dev/", whatever its name.
    Rules: build_staging_asset_folder R2."""
    CL.setting("CLOUDINARY_UPLOAD_ENV", "staging")
    result = M.build_staging_asset_folder(workspace_name="Acme", session_id=12)
    # Then 1
    assert result == "Dev/Acme/Mobile Staging/session-12"


# =========================================================================== #
# create_session_token
# =========================================================================== #

def test_mobs_tk_01__fixed_raw_and_its_hash(CL):
    """MOBS-TK-01 — the raw token is token_urlsafe(32) and the hash is its hash.
    Rules: create_session_token R1."""
    result = M.create_session_token()
    # Then 1
    assert result == ("fixed-raw-token", H("fixed-raw-token"))
    # Then 2
    CL.raw.assert_called_once_with(32)


def test_mobs_tk_02__real_tokens_43_chars_and_differ(CL):
    """MOBS-TK-02 — real tokens are 43 URL-safe characters and differ.
    Rules: create_session_token R1."""
    CL.real("raw")
    first = M.create_session_token()
    result = M.create_session_token()
    # Then 1
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", result[0]) is not None
    # Then 2
    assert result[0] != first[0]
    # Then 3
    assert result[1] == H(result[0])


# =========================================================================== #
# resolve_entity_label
# =========================================================================== #

def test_mobs_rl_01__client_label_trimmed(db, R):
    """MOBS-RL-01 — a client label is trimmed.
    Rules: resolve_entity_label R1."""
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label="  Box 7 ")
    # Then 1
    assert result == "Box 7"


def test_mobs_rl_02__client_label_cut_after_trim(db, R):
    """MOBS-RL-02 — a client label is cut to 80 after trimming.
    Rules: resolve_entity_label R1."""
    result = M.resolve_entity_label(
        db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label="   " + "a" * 79 + "bc ",
    )
    # Then 1
    assert result == "a" * 79 + "b"


def test_mobs_rl_03__none_uses_record_name(db, R):
    """MOBS-RL-03 — None uses the record's name.
    Rules: resolve_entity_label R2."""
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=None)
    # Then 1
    assert result == "Tender"


def test_mobs_rl_04__empty_label_uses_record_name(db, R):
    """MOBS-RL-04 — an empty label uses the record's name.
    Rules: resolve_entity_label R2."""
    MA = machine(db, R, "Press 1")
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.MACHINE, entity_id=MA.id, entity_label="")
    # Then 1
    assert result == "Press 1"


def test_mobs_rl_05__whitespace_label_uses_record_number(db, R):
    """MOBS-RL-05 — a whitespace-only label uses the record's number.
    Rules: resolve_entity_label R2."""
    TK = ticket(db, R, "HELP-2026-001")
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=" \t ")
    # Then 1
    assert result == "HELP-2026-001"


def test_mobs_rl_06__unknown_record_type_dash_id(db, R):
    """MOBS-RL-06 — an unknown record gives "<type>-<id>".
    Rules: resolve_entity_label R2."""
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=MISSING, entity_label=None)
    # Then 1
    assert result == "project-999999999"


def test_mobs_rl_07__scratch_label(db, R):
    """MOBS-RL-07 — scratch gives "scratch-<id>".
    Rules: resolve_entity_label R2."""
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.SCRATCH, entity_id=777, entity_label=None)
    # Then 1
    assert result == "scratch-777"


def test_mobs_rl_08__eighty_char_name_kept(db, R):
    """MOBS-RL-08 — a looked-up name of exactly 80 characters is kept whole.
    Rules: resolve_entity_label R3."""
    PL = proj(db, R, "L" * 80)
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=PL.id, entity_label=None)
    # Then 1
    assert result == "L" * 80


@XF2132
def test_mobs_rl_09__long_name_cut_to_80(db, R):
    """MOBS-RL-09 — a looked-up name of 120 characters is cut to 80.
    Rules: resolve_entity_label R3 [BUG-2132]."""
    PL = proj(db, R, "L" * 79 + "M" * 41)
    result = M.resolve_entity_label(db, workspace=R.W1, entity_type=ET.PROJECT, entity_id=PL.id, entity_label=None)
    # Then 1
    assert result == "L" * 79 + "M"


# =========================================================================== #
# create_session
# =========================================================================== #

def test_mobs_c_01__row_written_and_raw_returned(db, R):
    """MOBS-C-01 — the row is written as stated and the raw token returned.
    Rules: create_session R1, R2, R3."""
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=None)
    # Then 1
    assert result[1] == "fixed-raw-token"
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.workspace_id == R.W1.id
    assert row.created_by == R.UG.id
    assert row.entity_type == "project"
    assert row.entity_id == R.P1.id
    assert row.entity_label == "Tender"
    # Then 3
    assert row.token_hash == H("fixed-raw-token")
    assert row.status == "waiting"
    assert row.delivery_type == "authenticated"
    # Then 4
    for col in ("public_id", "asset_folder", "resource_type", "format", "version", "file_name", "mime_type", "file_size"):
        assert getattr(row, col) is None, col
    # Then 5
    assert row.created_at is not None
    assert row.updated_at is not None
    # Then 6
    assert row.expires_at == NOW_UTC + timedelta(minutes=10)
    # Then 7
    assert count(db, "mobile_upload_sessions", "token_hash = 'fixed-raw-token'") == 0


@XF1282
def test_mobs_c_02__expiry_true_moment_in_any_zone(db, R):
    """MOBS-C-02 — the stored expiry is a true moment in any database zone.
    Rules: create_session R4 [BUG-1282]."""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))  # zone NY
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=None)
    # Then 1
    assert result[1] == "fixed-raw-token"
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.expires_at == datetime(2026, 3, 5, 12, 10, 0, tzinfo=timezone.utc)


def test_mobs_c_03__client_label_stored_trimmed(db, R):
    """MOBS-C-03 — a client label is stored trimmed.
    Rules: create_session R1, resolve_entity_label R1."""
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=" Box 7 ")
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_label == "Box 7"


def test_mobs_c_04__second_session_is_new_row(db, R):
    """MOBS-C-04 — a second session for the same user and record is a new row.
    Rules: create_session R7."""
    S0 = add(db, sess(R))
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=None)
    # Then 1
    assert result[0].id != S0.id
    # Then 2
    assert count(db, "mobile_upload_sessions", "created_by = :u AND entity_id = :e", u=R.UG.id, e=R.P1.id) == 2
    # Then 3
    row = reread(db, MobileUploadSession, S0.id)
    assert row.token_hash == H("raw-token-1")
    assert row.status == "waiting"


def test_mobs_c_05__scratch_needs_no_record(db, R):
    """MOBS-C-05 — scratch needs no record.
    Rules: create_session R5 (scratch)."""
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SCRATCH, entity_id=777, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_type == "scratch"
    assert row.entity_id == 777
    assert row.entity_label == "scratch-777"


@XF2132
def test_mobs_c_06__long_record_name_no_longer_fails(db, R):
    """MOBS-C-06 — a 120-character record name no longer fails the write.
    Rules: create_session (label), resolve_entity_label R3 [BUG-2132]."""
    PL = proj(db, R, "L" * 120)
    # Then 1 (the call itself raises DataError at the flush today)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PL.id, entity_label=None)
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_label == "L" * 80


def test_mobs_c_07__flushes_never_commits(db, R):
    """MOBS-C-07 — create flushes and never commits.
    Rules: create_session (Side effects)."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=R.P1.id, entity_label=None)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert count(db, "mobile_upload_sessions", "created_by = :u", u=R.UG.id) == 0


@XF2130
def test_mobs_c_08__unknown_project_refused(db, R, CL):
    """MOBS-C-08 — PR-1: an unknown project is refused.
    Rules: create_session R5 [BUG-2130]."""
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=MISSING, entity_label=None)
    # Then 2
    assert str(exc.value) == "project 999999999 not found."
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_09__w0_project_refused(db, R, CL):
    """MOBS-C-09 — PR-1: a W0 project (lower workspace id) is refused.
    Rules: create_session R5 [BUG-2130]."""
    PX = proj(db, R, "Zero Job", where="W0")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PX.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PX.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_10__w2_project_refused(db, R, CL):
    """MOBS-C-10 — PR-1: a W2 project (higher workspace id) is refused.
    Rules: create_session R5 [BUG-2130]."""
    PX = proj(db, R, "Nine Job", where="W2")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PX.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PX.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_11__deleted_project_refused(db, R, CL):
    """MOBS-C-11 — PR-1: a soft-deleted project is refused.
    Rules: create_session R5 [BUG-2130]."""
    PD = proj(db, R, "Old Job", deleted=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PD.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PD.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_12__deleted_machine_refused(db, R, CL):
    """MOBS-C-12 — PR-1: a soft-deleted machine is refused.
    Rules: create_session R5 [BUG-2130]."""
    MD = machine(db, R, "Press 4", deleted=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.MACHINE, entity_id=MD.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("machine", MD.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_13__deleted_work_order_refused(db, R, CL):
    """MOBS-C-13 — PR-1: a soft-deleted work order is refused.
    Rules: create_session R5 [BUG-2130]."""
    WD = wo(db, R, "WO-3", deleted=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.WORK_ORDER, entity_id=WD.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("work_order", WD.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_14__component_of_deleted_project_refused(db, R, CL):
    """MOBS-C-14 — PR-1: a live component of a deleted project is refused.
    Rules: create_session R5 [BUG-2130]."""
    PD = proj(db, R, "Old Job", deleted=True)
    CD = comp(db, PD, "Frame")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=CD.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project_component", CD.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_15__w2_purchase_order_refused(db, R, CL):
    """MOBS-C-15 — PR-1: a W2 purchase order is refused.
    Rules: create_session R5 [BUG-2130]."""
    O9 = po(db, R, "PO-T-009", workspace_id=R.W2.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PURCHASE_ORDER, entity_id=O9.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("purchase_order", O9.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_16__w0_ticket_refused_even_to_owner(db, R, CL):
    """MOBS-C-16 — PR-1: a W0 help ticket is refused, even to a W1 owner-role member.
    Rules: create_session R5 [BUG-2130]."""
    mg_but(db, R, role="owner")
    T0X = ticket(db, R, "HELP-2026-001", workspace_id=R.W0.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=T0X.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", T0X.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_17__po_id_only_a_machine_has_refused(db, R, CL):
    """MOBS-C-17 — PR-1: a purchase-order id that only a W1 machine has is refused.
    Rules: create_session R5 [BUG-2130]."""
    machine(db, R, "Press 7", id=XID(1))  # no purchase order has id XID(1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PURCHASE_ORDER, entity_id=XID(1), entity_label=None)
    # Then 2
    assert str(exc.value) == NF("purchase_order", XID(1))
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2130
def test_mobs_c_18__component_id_only_a_project_has_refused(db, R, CL):
    """MOBS-C-18 — PR-1: a component id that only a live W1 project has is refused.
    Rules: create_session R5 [BUG-2130]."""
    proj(db, R, "Yard", id=XID(2))  # no project component has id XID(2)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=XID(2), entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project_component", XID(2))
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


def test_mobs_c_19__live_machine_passes(db, R):
    """MOBS-C-19 — PR-1 passes: a live W1 machine.
    Rules: create_session R5 [BUG-2130]."""
    MA = machine(db, R, "Press 1")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.MACHINE, entity_id=MA.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_type == "machine"
    assert row.entity_id == MA.id
    assert row.entity_label == "Press 1"


def test_mobs_c_20__live_component_passes(db, R):
    """MOBS-C-20 — PR-1 passes: a live component of a live project.
    Rules: create_session R5 [BUG-2130]."""
    CA = comp(db, R.P1, "Frame")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=CA.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_type == "project_component"
    assert row.entity_id == CA.id
    assert row.entity_label == "Frame"


def test_mobs_c_21__scratch_any_id_passes(db, R):
    """MOBS-C-21 — PR-1 passes: scratch with an id no table has.
    Rules: create_session R5 [BUG-2130]."""
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SCRATCH, entity_id=MISSING, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_label == "scratch-999999999"


def test_mobs_c_22__plain_member_opens_purchase_order(db, R):
    """MOBS-C-22 — PR-2 passes: a plain member opens a W1 purchase order.
    Rules: create_session R6 [BUG-2131]."""
    O1 = po(db, R, "PO-T-001")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PURCHASE_ORDER, entity_id=O1.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_label == "PO-T-001"


@XF2131
def test_mobs_c_23__plain_member_private_project_refused(db, R, CL):
    """MOBS-C-23 — PR-2: a plain member is refused a private project.
    Rules: create_session R6 [BUG-2131]."""
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_24__owning_w0_private_refused(db, R):
    """MOBS-C-24 — PR-2: owning W0 does not open a W1 private project.
    Rules: create_session R6 [BUG-2131]."""
    set_owner(db, R.W0, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_25__owning_w2_private_refused(db, R):
    """MOBS-C-25 — PR-2: owning W2 does not open a W1 private project.
    Rules: create_session R6 [BUG-2131]."""
    set_owner(db, R.W2, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_26__privileged_only_in_w0_refused(db, R):
    """MOBS-C-26 — PR-2: privileged only in W0 does not open it.
    Rules: create_session R6 [BUG-2131]."""
    member(db, R, R.UG, "owner", ws=R.W0)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_27__privileged_only_in_w2_refused(db, R):
    """MOBS-C-27 — PR-2: privileged only in W2 does not open it.
    Rules: create_session R6 [BUG-2131]."""
    member(db, R, R.UG, "ground-team-manager", ws=R.W2)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_28__other_private_memberships_refused(db, R):
    """MOBS-C-28 — PR-2: membership of other private projects (lower and higher id) does not open it.
    Rules: create_session R6 [BUG-2131]."""
    PA = proj(db, R, "Alpha", private=True)
    pmem(db, R, PA, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    PB = proj(db, R, "Beta", private=True)
    pmem(db, R, PB, R.UG)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_29__creator_of_other_private_refused(db, R):
    """MOBS-C-29 — PR-2: having created another private project does not open this one.
    Rules: create_session R6 [BUG-2131]."""
    proj(db, R, "Alpha", private=True, created_by=R.UG.id)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_30__private_no_creator_refused(db, R):
    """MOBS-C-30 — PR-2: a private project with no creator is closed to a plain member.
    Rules: create_session R6 [BUG-2131]."""
    PV = proj(db, R, "Tender 2027", private=True, created_by=None)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_31__suspended_owner_refused(db, R):
    """MOBS-C-31 — PR-2: a suspended W1 owner membership does not open it.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="owner", status="suspended")
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_32__component_of_private_refused(db, R):
    """MOBS-C-32 — PR-2: a component of a private project is closed to a plain member.
    Rules: create_session R6 [BUG-2131]."""
    PV = proj(db, R, "Tender 2027", private=True)
    CV = comp(db, PV, "Frame")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=CV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project_component", CV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_33__other_members_ticket_refused(db, R, CL):
    """MOBS-C-33 — PR-2: another member's help ticket is closed to a plain role.
    Rules: create_session R6 [BUG-2131]."""
    TK = ticket(db, R, "HELP-2026-001")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_34__creator_of_other_tickets_refused(db, R):
    """MOBS-C-34 — PR-2: creating other tickets (lower and higher id) does not open this one.
    Rules: create_session R6 [BUG-2131]."""
    ticket(db, R, "HELP-2026-001", created_by=R.UG.id)
    TK = ticket(db, R, "HELP-2026-002")
    ticket(db, R, "HELP-2026-003", created_by=R.UG.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_35__ticket_no_creator_refused(db, R):
    """MOBS-C-35 — PR-2: a ticket with no creator is closed to a plain role.
    Rules: create_session R6 [BUG-2131]."""
    TK = ticket(db, R, "HELP-2026-001", created_by=None)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@XF2131
def test_mobs_c_36__capital_owner_role_refused(db, R):
    """MOBS-C-36 — PR-2: a W1 membership role "Owner" with a capital does not open a ticket.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="Owner")
    TK = ticket(db, R, "HELP-2026-001")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_mobs_c_37__w1_owner_opens_private(db, R):
    """MOBS-C-37 — PR-2 grant: the W1 owner opens a private project.
    Rules: create_session R6 [BUG-2131]."""
    set_owner(db, R.W1, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_id == PV.id
    assert row.entity_label == "Tender 2027"


def test_mobs_c_38__active_gtm_opens_private(db, R):
    """MOBS-C-38 — PR-2 grant: an active ground-team-manager opens a private project.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="ground-team-manager")
    PV = proj(db, R, "Tender 2027", private=True)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_id == PV.id


def test_mobs_c_39__creator_opens_private(db, R):
    """MOBS-C-39 — PR-2 grant: the creator opens their private project.
    Rules: create_session R6 [BUG-2131]."""
    PV = proj(db, R, "Tender 2027", private=True, created_by=R.UG.id)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_id == PV.id


def test_mobs_c_40__project_member_opens_private_component(db, R):
    """MOBS-C-40 — PR-2 grant: a project member opens a component of a private project.
    Rules: create_session R6 [BUG-2131]."""
    PV = proj(db, R, "Tender 2027", private=True)
    pmem(db, R, PV, R.UG)
    CV = comp(db, PV, "Frame")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=CV.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_id == CV.id
    assert row.entity_label == "Frame"


def test_mobs_c_41__ticket_creator_opens_it(db, R):
    """MOBS-C-41 — PR-2 grant: the ticket's creator opens it.
    Rules: create_session R6 [BUG-2131]."""
    TK = ticket(db, R, "HELP-2026-001", created_by=R.UG.id)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_label == "HELP-2026-001"


def test_mobs_c_42__active_gtm_opens_others_ticket(db, R):
    """MOBS-C-42 — PR-2 grant: an active ground-team-manager opens another member's ticket.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="ground-team-manager")
    TK = ticket(db, R, "HELP-2026-001")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_id == TK.id


def test_mobs_c_43__platform_admin_opens_creatorless_ticket(db, R):
    """MOBS-C-43 — PR-2 grant: a platform admin opens a ticket with no creator.
    Rules: create_session R6 [BUG-2131]."""
    R.UG.is_platform_admin = True
    db.flush()
    TK = ticket(db, R, "HELP-2026-001", created_by=None)
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    assert reread(db, MobileUploadSession, result[0].id).entity_id == TK.id


@XF2131
def test_mobs_c_44__removed_owner_private_refused(db, R, CL):
    """MOBS-C-44 — PR-2: a removed (inactive) W1 owner membership does not open a private project.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="owner", **REMOVED)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_45__suspended_gtm_ticket_refused(db, R, CL):
    """MOBS-C-45 — PR-2: a suspended W1 ground-team-manager membership does not open another member's ticket.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="ground-team-manager", status="suspended")
    TK = ticket(db, R, "HELP-2026-001")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_46__removed_owner_ticket_refused(db, R, CL):
    """MOBS-C-46 — PR-2: a removed (inactive) W1 owner membership does not open another member's ticket.
    Rules: create_session R6 [BUG-2131]."""
    mg_but(db, R, role="owner", **REMOVED)
    TK = ticket(db, R, "HELP-2026-001")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_47__older_privileged_rows_elsewhere_refused(db, R, CL):
    """MOBS-C-47 — PR-2: privileged rows in W0 and W2 older than the W1 row do not open a private project.
    Rules: create_session R6 [BUG-2131]."""
    drop_mg(db, R)
    member(db, R, R.UG, "owner", ws=R.W0)
    member(db, R, R.UG, "ground-team-manager", ws=R.W2)
    member(db, R, R.UG, "ground-team")  # the W1 row, now the newest
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_48__owner_only_in_w0_ticket_refused(db, R, CL):
    """MOBS-C-48 — PR-2: an owner role only in W0 does not open another member's W1 ticket.
    Rules: create_session R6 [BUG-2131]."""
    member(db, R, R.UG, "owner", ws=R.W0)
    TK = ticket(db, R, "HELP-2026-001")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


def test_mobs_c_49__non_member_opens_workspace_machine(db, R):
    """MOBS-C-49 — PR-2 passes: a caller with no W1 membership opens a workspace-wide machine.
    Rules: create_session R6 [BUG-2131]."""
    drop_mg(db, R)
    MA = machine(db, R, "Press 1")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.MACHINE, entity_id=MA.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_type == "machine"
    assert row.entity_id == MA.id
    assert row.entity_label == "Press 1"


@XF2131
def test_mobs_c_50__no_membership_private_refused(db, R, CL):
    """MOBS-C-50 — PR-2: no W1 membership at all: a private project stays closed.
    Rules: create_session R6 [BUG-2131]."""
    drop_mg(db, R)
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_51__platform_admin_no_membership_private_refused(db, R, CL):
    """MOBS-C-51 — PR-2: a platform admin with no W1 membership is refused a private project.
    Rules: create_session R6 [BUG-2131]."""
    drop_mg(db, R)
    R.UG.is_platform_admin = True
    db.flush()
    PV = proj(db, R, "Tender 2027", private=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT, entity_id=PV.id, entity_label=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


@XF2131
def test_mobs_c_52__platform_admin_no_membership_private_component_refused(db, R, CL):
    """MOBS-C-52 — PR-2: a platform admin with no W1 membership is refused a component of a private project.
    Rules: create_session R6 [BUG-2131]."""
    drop_mg(db, R)
    R.UG.is_platform_admin = True
    db.flush()
    PV = proj(db, R, "Tender 2027", private=True)
    CV = comp(db, PV, "Frame")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.create_session(
            db, workspace=R.W1, user=R.UG, entity_type=ET.PROJECT_COMPONENT, entity_id=CV.id, entity_label=None,
        )
    # Then 2
    assert str(exc.value) == NF("project_component", CV.id)
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_called(CL) == []


def test_mobs_c_53__workspace_owner_plain_role_opens_others_ticket(db, R):
    """MOBS-C-53 — PR-2 grant: the workspace owner with a plain role opens another member's ticket.
    Rules: create_session R6 [BUG-2131, BUG-2103]."""
    set_owner(db, R.W1, R.UG)
    TK = ticket(db, R, "HELP-2026-001")
    result = M.create_session(db, workspace=R.W1, user=R.UG, entity_type=ET.SUPPORT_TICKET, entity_id=TK.id, entity_label=None)
    # Then 1
    assert result[0].id is not None
    # Then 2
    row = reread(db, MobileUploadSession, result[0].id)
    assert row.entity_type == "support_ticket"
    assert row.entity_id == TK.id
    assert row.created_by == R.UG.id


# =========================================================================== #
# to_create_response
# =========================================================================== #

def test_mobs_cr_01__create_response_fields(db, R):
    """MOBS-CR-01 — the create response carries id, token, expiry and label.
    Rules: to_create_response R1."""
    S = add(db, sess(R))
    result = M.to_create_response(S, "raw-token-1")
    # Then 1
    assert result.session_id == S.id
    assert result.token == "raw-token-1"
    # Then 2
    assert result.expires_at == LATER
    assert result.entity_label == "Tender"


# =========================================================================== #
# _ensure_active
# =========================================================================== #

def test_mobs_ea_01__consumed_no_longer_available(R):
    """MOBS-EA-01 — consumed is no longer available, even before its time.
    Rules: _ensure_active R1."""
    S = sess(R, status="consumed")
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session is no longer available."
    # Then 3
    assert S.status == "consumed"


def test_mobs_ea_02__cancelled_no_longer_available(R):
    """MOBS-EA-02 — cancelled is no longer available.
    Rules: _ensure_active R1."""
    S = sess(R, status="cancelled")
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session is no longer available."
    # Then 3
    assert S.status == "cancelled"


def test_mobs_ea_03__expired_keeps_no_longer_available(R):
    """MOBS-EA-03 — expired past its time keeps the "no longer available" answer.
    Rules: _ensure_active R1."""
    S = sess(R, status="expired", expires_at=PAST)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session is no longer available."
    # Then 3
    assert S.status == "expired"


def test_mobs_ea_04__waiting_exactly_at_time_expired(R):
    """MOBS-EA-04 — waiting exactly at its time is expired.
    Rules: _ensure_active R2."""
    S = sess(R, expires_at=NOW_UTC)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session has expired."
    # Then 3
    assert S.status == "expired"


def test_mobs_ea_05__one_microsecond_before_returned(R):
    """MOBS-EA-05 — waiting one microsecond before its time is returned.
    Rules: _ensure_active R2, R5."""
    S = sess(R, expires_at=NOW_UTC + US)
    result = M._ensure_active(S)
    # Then 1
    assert result is S
    # Then 2
    assert S.status == "waiting"


def test_mobs_ea_06__uploaded_past_time_expired(R):
    """MOBS-EA-06 — uploaded past its time is expired on the phone path.
    Rules: _ensure_active R2."""
    S = sess(R, "uploaded", expires_at=PAST)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session has expired."
    # Then 3
    assert S.status == "expired"


def test_mobs_ea_07__naive_expiry_compared_as_utc(R):
    """MOBS-EA-07 — a naive expiry is compared as UTC.
    Rules: _ensure_active R3."""
    S = sess(R, expires_at=NOW)
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session has expired."


@XF1282
def test_mobs_ea_08__plus_six_past_true_moment_expired(R):
    """MOBS-EA-08 — +06:00 one second past its true moment is expired.
    Rules: _ensure_active R3 [BUG-1282]."""
    S = sess(R, expires_at=datetime(2026, 3, 5, 17, 59, 59, tzinfo=P6))  # 11:59:59 UTC
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M._ensure_active(S)
    # Then 2
    assert str(exc.value) == "Upload session has expired."


@XF1282
def test_mobs_ea_09__minus_five_hour_ahead_still_active(R):
    """MOBS-EA-09 — −05:00 one hour ahead of now is still active.
    Rules: _ensure_active R3 [BUG-1282]."""
    S = sess(R, expires_at=datetime(2026, 3, 5, 8, 0, 0, tzinfo=M5))  # 13:00 UTC
    # Then 1 (the call itself raises MobileUploadSessionNotFoundError today)
    result = M._ensure_active(S)
    assert result is S
    # Then 2
    assert S.status == "waiting"


def test_mobs_ea_10__expired_in_memory_only(db, R):
    """MOBS-EA-10 — "expired" stays in memory; the stored row still says waiting.
    Rules: _ensure_active R4."""
    S = add(db, sess(R, expires_at=PAST))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError):
        M._ensure_active(S)
    # Then 2
    assert S in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count(db, "mobile_upload_sessions", "id = :i AND status = 'waiting'", i=S.id) == 1


def test_mobs_ea_11__active_row_untouched(db, R):
    """MOBS-EA-11 — an active stored row is returned untouched.
    Rules: _ensure_active R5."""
    S = add(db, sess(R, "uploaded"))
    result = M._ensure_active(S)
    # Then 1
    assert result is S
    # Then 2
    assert not db.dirty


# =========================================================================== #
# get_by_raw_token
# =========================================================================== #

def test_mobs_t_01__found_among_others_any_workspace(db, R):
    """MOBS-T-01 — the session of that token is found among others, in any workspace.
    Rules: get_by_raw_token R1, R3."""
    add(db, sess(R, token_hash=H(RAW0)))
    S9 = add(db, sess(R, workspace_id=R.W2.id, token_hash=H(RAW1)))
    add(db, sess(R, token_hash=H(RAW2)))
    result = M.get_by_raw_token(db, raw_token="raw-token-1")
    # Then 1
    assert result is S9
    # Then 2
    assert not db.dirty


def test_mobs_t_02__unknown_token_not_found(db, R):
    """MOBS-T-02 — an unknown token is not found.
    Rules: get_by_raw_token R2."""
    add(db, sess(R))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_by_raw_token(db, raw_token="raw-token-9")
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_t_03__token_compares_exactly(db, R):
    """MOBS-T-03 — the token compares exactly (capitals do not match).
    Rules: get_by_raw_token R2."""
    add(db, sess(R))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_by_raw_token(db, raw_token="RAW-TOKEN-1")
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_t_04__hash_not_accepted_as_token(db, R):
    """MOBS-T-04 — the hash itself is not accepted as a token.
    Rules: get_by_raw_token R1, R2."""
    add(db, sess(R))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_by_raw_token(db, raw_token=H("raw-token-1"))
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_t_05__cancelled_no_longer_available(db, R):
    """MOBS-T-05 — a found cancelled session is no longer available.
    Rules: get_by_raw_token R3."""
    add(db, sess(R, status="cancelled"))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_by_raw_token(db, raw_token="raw-token-1")
    # Then 2
    assert str(exc.value) == "Upload session is no longer available."


def test_mobs_t_06__waiting_past_time_expired(db, R):
    """MOBS-T-06 — a found waiting session past its time is expired.
    Rules: get_by_raw_token R3."""
    S = add(db, sess(R, expires_at=PAST))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_by_raw_token(db, raw_token="raw-token-1")
    # Then 2
    assert str(exc.value) == "Upload session has expired."
    # Then 3
    assert S.status == "expired"
    # Then 4
    assert S in db.dirty


# =========================================================================== #
# get_for_creator
# =========================================================================== #

def test_mobs_gc_01__own_session_among_others(db, R):
    """MOBS-GC-01 — the caller's own session is returned among others.
    Rules: get_for_creator R1."""
    add(db, sess(R, token_hash=H(RAW0)))
    S = add(db, sess(R))
    add(db, sess(R, token_hash=H(RAW2)))
    result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 1
    assert result is S
    # Then 2
    assert not db.dirty


def test_mobs_gc_02__w0_session_not_found(db, R):
    """MOBS-GC-02 — a W0 session of the caller is not found from W1.
    Rules: get_for_creator R1."""
    S0 = add(db, sess(R, workspace_id=R.W0.id))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=S0.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_gc_03__w2_session_not_found(db, R):
    """MOBS-GC-03 — a W2 session of the caller is not found from W1.
    Rules: get_for_creator R1."""
    S9 = add(db, sess(R, workspace_id=R.W2.id))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=S9.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_gc_04__lower_id_members_session_not_found(db, R):
    """MOBS-GC-04 — another member's session (lower user id) is not found.
    Rules: get_for_creator R1."""
    S = add(db, sess(R, created_by=R.U1.id))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_gc_05__higher_id_members_session_not_found(db, R):
    """MOBS-GC-05 — another member's session (higher user id) is not found.
    Rules: get_for_creator R1."""
    UH = make_profile(db, name="Zed Ali")
    member(db, R, UH, "ground-team")
    S = add(db, sess(R, created_by=UH.id))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_gc_06__unknown_id_not_found(db, R):
    """MOBS-GC-06 — an unknown id is not found.
    Rules: get_for_creator R1."""
    add(db, sess(R))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=MISSING, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session not found."


def test_mobs_gc_07__waiting_at_time_expired_in_memory(db, R):
    """MOBS-GC-07 — waiting exactly at its time is expired, in memory only.
    Rules: get_for_creator R2, R3."""
    S = add(db, sess(R, expires_at=NOW_UTC))
    # Then 1
    with pytest.raises(MobileUploadSessionNotFoundError) as exc:
        M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 2
    assert str(exc.value) == "Upload session has expired."
    # Then 3
    assert S in db.dirty
    # Then 4
    assert count(db, "mobile_upload_sessions", "id = :i AND status = 'waiting'", i=S.id) == 1


def test_mobs_gc_08__one_microsecond_before_returned(db, R):
    """MOBS-GC-08 — waiting one microsecond before its time is returned.
    Rules: get_for_creator R2."""
    S = add(db, sess(R, expires_at=NOW_UTC + US))
    result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 1
    assert result is S
    # Then 2
    assert S.status == "waiting"


def test_mobs_gc_09__uploaded_past_time_returned(db, R):
    """MOBS-GC-09 — uploaded past its time is still returned to the desktop.
    Rules: get_for_creator R4."""
    S = add(db, sess(R, "uploaded", expires_at=PAST))
    result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 1
    assert result is S
    # Then 2
    assert S.status == "uploaded"


def test_mobs_gc_10__consumed_past_time_returned(db, R):
    """MOBS-GC-10 — consumed and past its time is returned.
    Rules: get_for_creator R4."""
    S = add(db, sess(R, status="consumed", expires_at=PAST))
    result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 1
    assert result is S
    # Then 2
    assert S.status == "consumed"


def test_mobs_gc_11__cancelled_returned(db, R):
    """MOBS-GC-11 — cancelled is returned.
    Rules: get_for_creator R4."""
    S = add(db, sess(R, status="cancelled"))
    result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id)
    # Then 1
    assert result is S
    # Then 2
    assert S.status == "cancelled"


# [claude] MOBS-GC-12
@XF2139
def test_mobs_gc_12__promote_cancel_read_locks_row(db, R):
    """MOBS-GC-12 — the promote / cancel read locks the row.
    Rules: get_for_creator R5, cancel_session R6, promote_to_attachment R11 [BUG-2139]."""
    S = add(db, sess(R, "uploaded"))
    db.expire_all()
    stmts, stop = recorder(db)
    try:
        # Then 1 (the call itself raises TypeError today: no `for_update` option)
        result = M.get_for_creator(db, session_id=S.id, workspace_id=R.W1.id, user_id=R.UG.id, for_update=True)
    finally:
        stop()
    assert result.id == S.id
    # Then 2
    assert any(
        s.lstrip().upper().startswith("SELECT") and "mobile_upload_sessions" in s and "FOR UPDATE" in s.upper()
        for s in stmts
    )


# =========================================================================== #
# _staging_preview_url
# =========================================================================== #

def test_mobs_pv_01__staged_image_signed_preview(db, R, CL):
    """MOBS-PV-01 — a staged image gives a signed 400-px preview.
    Rules: _staging_preview_url R4."""
    S = add(db, sess(R, "uploaded"))
    result = M._staging_preview_url(S)
    # Then 1
    assert result == "https://signed.example/preview"
    # Then 2
    CL.bsdu.assert_called_once()
    assert kw(CL.bsdu)["public_id"] == STG
    assert kw(CL.bsdu)["resource_type"] == "image"
    assert kw(CL.bsdu)["delivery_type"] == "authenticated"
    # Then 3
    assert kw(CL.bsdu)["version"] == 1700000000
    assert type(kw(CL.bsdu)["version"]) is int
    # Then 4
    assert kw(CL.bsdu)["fmt"] == "jpg"
    assert kw(CL.bsdu)["transformation"] == [{"width": 400, "crop": "limit"}]


def test_mobs_pv_02__missing_types_default(db, R, CL):
    """MOBS-PV-02 — missing resource and delivery types default to image / authenticated.
    Rules: _staging_preview_url R4."""
    S = add(db, sess(R, "uploaded", resource_type=None, delivery_type=None))
    S.delivery_type = None  # NOT NULL column: the flush stored its default; the card's None is kept in memory
    result = M._staging_preview_url(S)
    # Then 1
    assert result == "https://signed.example/preview"
    # Then 2
    assert kw(CL.bsdu)["resource_type"] == "image"
    assert kw(CL.bsdu)["delivery_type"] == "authenticated"


def test_mobs_pv_03__waiting_no_preview(db, R, CL):
    """MOBS-PV-03 — a waiting session has no preview.
    Rules: _staging_preview_url R1."""
    S = add(db, sess(R, "uploaded", status="waiting"))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None
    # Then 2
    assert CL.bsdu.called is False


def test_mobs_pv_04__empty_public_id_no_preview(db, R, CL):
    """MOBS-PV-04 — an empty public_id gives no preview.
    Rules: _staging_preview_url R2."""
    S = add(db, sess(R, "uploaded", public_id=""))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None
    # Then 2
    assert CL.bsdu.called is False


def test_mobs_pv_05__version_zero_no_preview(db, R, CL):
    """MOBS-PV-05 — version 0 gives no preview.
    Rules: _staging_preview_url R2."""
    S = add(db, sess(R, "uploaded", version=0))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None
    # Then 2
    assert CL.bsdu.called is False


def test_mobs_pv_06__missing_format_no_preview(db, R, CL):
    """MOBS-PV-06 — a missing format gives no preview.
    Rules: _staging_preview_url R2."""
    S = add(db, sess(R, "uploaded", format=None))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None
    # Then 2
    assert CL.bsdu.called is False


def test_mobs_pv_07__pdf_no_preview(db, R, CL):
    """MOBS-PV-07 — a PDF gives no preview.
    Rules: _staging_preview_url R3."""
    S = add(db, sess(R, "uploaded", file_name="scan.pdf", mime_type="application/pdf", format="pdf"))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None
    # Then 2
    assert CL.bsdu.called is False


def test_mobs_pv_08__missing_mime_no_preview(db, R):
    """MOBS-PV-08 — a missing MIME type gives no preview.
    Rules: _staging_preview_url R3."""
    S = add(db, sess(R, "uploaded", mime_type=None))
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None


def test_mobs_pv_09__capital_image_mime_is_image(db, R):
    """MOBS-PV-09 — "IMAGE/JPEG" in capitals is an image.
    Rules: _staging_preview_url R3."""
    S = add(db, sess(R, "uploaded", mime_type="IMAGE/JPEG"))
    result = M._staging_preview_url(S)
    # Then 1
    assert result == "https://signed.example/preview"


def test_mobs_pv_10__not_configured_gives_none(db, R, CL):
    """MOBS-PV-10 — "not configured" while building gives None.
    Rules: _staging_preview_url R5."""
    S = add(db, sess(R, "uploaded"))
    CL.bsdu.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None


def test_mobs_pv_11__other_error_gives_none(db, R, CL):
    """MOBS-PV-11 — any other error while building gives None.
    Rules: _staging_preview_url R5."""
    S = add(db, sess(R, "uploaded"))
    CL.bsdu.side_effect = RuntimeError("boom")
    result = M._staging_preview_url(S)
    # Then 1
    assert result is None


# =========================================================================== #
# to_session_response
# =========================================================================== #

def test_mobs_sr_01__desktop_response_no_cloudinary_id(db, R):
    """MOBS-SR-01 — the desktop response carries the row's fields and no Cloudinary id.
    Rules: to_session_response R1."""
    S = add(db, sess(R, "uploaded"))
    result = M.to_session_response(S)
    # Then 1
    assert result.id == S.id
    assert result.status == MobileUploadSessionStatusEnum.UPLOADED
    assert result.entity_type == ET.PROJECT
    # Then 2
    assert result.entity_id == R.P1.id
    assert result.entity_label == "Tender"
    assert result.expires_at == LATER
    # Then 3
    assert result.file_name == "photo.jpg"
    assert result.mime_type == "image/jpeg"
    assert result.file_size == 2048
    # Then 4
    assert result.preview_url == "https://signed.example/preview"
    # Then 5
    assert "public_id" not in result.model_dump()
    assert STG not in str(result.model_dump())


def test_mobs_sr_02__waiting_no_preview(db, R):
    """MOBS-SR-02 — a waiting session has no preview.
    Rules: to_session_response R1."""
    S = add(db, sess(R))
    result = M.to_session_response(S)
    # Then 1
    assert result.status == MobileUploadSessionStatusEnum.WAITING
    assert result.preview_url is None
    assert result.file_name is None


def test_mobs_sr_03__status_outside_enum_raises(R):
    """MOBS-SR-03 — a status outside the enum raises ValueError.
    Rules: to_session_response (Errors)."""
    S = sess(R, id=5, status="bogus")
    # Then 1
    with pytest.raises(ValueError):
        M.to_session_response(S)


# =========================================================================== #
# to_public_response
# =========================================================================== #

def test_mobs_pb_01__phone_sees_status_label_expiry(db, R):
    """MOBS-PB-01 — the phone sees status, label and expiry only.
    Rules: to_public_response R1."""
    S = add(db, sess(R, "uploaded"))
    result = M.to_public_response(S)
    # Then 1
    assert set(result.model_dump()) == {"status", "entity_label", "expires_at"}
    # Then 2
    assert result.status == MobileUploadSessionStatusEnum.UPLOADED
    assert result.entity_label == "Tender"
    assert result.expires_at == LATER


# =========================================================================== #
# normalize_public_sign
# =========================================================================== #

def test_mobs_np_01__same_as_desktop_scratch_request():
    """MOBS-NP-01 — the result is the desktop normalizer's for a scratch request.
    Rules: normalize_public_sign R1."""
    expected = attachment_manager.normalize_upload_request(AttachmentSignRequest(
        entity_type="scratch", entity_id=1, file_name=" photo.jpg ", mime_type="image/jpeg", file_size=1234,
    ))
    result = M.normalize_public_sign(file_name=" photo.jpg ", mime_type="image/jpeg", file_size=1234)
    # Then 1
    assert result == expected
    # Then 2
    assert result.file_name == "photo.jpg"
    assert result.resource_type == "image"


def test_mobs_np_02__max_bytes_accepted():
    """MOBS-NP-02 — exactly 10 485 760 bytes is accepted.
    Rules: normalize_public_sign R1."""
    result = M.normalize_public_sign(file_name="scan.pdf", mime_type="application/pdf", file_size=10485760)
    # Then 1
    assert result.file_name == "scan.pdf"
    assert result.resource_type == "image"


def test_mobs_np_03__one_byte_over_too_large():
    """MOBS-NP-03 — 10 485 761 bytes is too large.
    Rules: normalize_public_sign R1."""
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.normalize_public_sign(file_name="scan.pdf", mime_type="application/pdf", file_size=10485761)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."


def test_mobs_np_04__mime_mismatch_refused():
    """MOBS-NP-04 — a MIME type that does not match the extension is refused.
    Rules: normalize_public_sign R1."""
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.normalize_public_sign(file_name="photo.png", mime_type="image/jpeg", file_size=10)
    # Then 2
    assert str(exc.value) == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."


def test_mobs_np_05__unsupported_extension_refused():
    """MOBS-NP-05 — an unsupported extension is refused.
    Rules: normalize_public_sign R1."""
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.normalize_public_sign(file_name="archive.ZIP", mime_type="application/zip", file_size=10)
    # Then 2
    assert str(exc.value) == "Unsupported file extension: .zip"


def test_mobs_np_06__size_zero_outside_schema():
    """MOBS-NP-06 — size 0 is outside the request schema.
    Rules: normalize_public_sign R2."""
    # Then 1
    with pytest.raises(ValidationError):
        M.normalize_public_sign(file_name="photo.jpg", mime_type="image/jpeg", file_size=0)


def test_mobs_np_07__empty_name_outside_schema():
    """MOBS-NP-07 — an empty file name is outside the request schema.
    Rules: normalize_public_sign R2."""
    # Then 1
    with pytest.raises(ValidationError):
        M.normalize_public_sign(file_name="", mime_type="image/jpeg", file_size=10)


def test_mobs_np_08__256_chars_outside_255_not():
    """MOBS-NP-08 — a 256-character name is outside the schema; 255 is not.
    Rules: normalize_public_sign R2."""
    ok = M.normalize_public_sign(file_name="a" * 251 + ".jpg", mime_type="image/jpeg", file_size=10)
    # Then 1
    with pytest.raises(ValidationError):
        M.normalize_public_sign(file_name="a" * 252 + ".jpg", mime_type="image/jpeg", file_size=10)
    # Then 2
    assert ok.file_name == "a" * 251 + ".jpg"


def test_mobs_np_09__empty_mime_outside_schema():
    """MOBS-NP-09 — an empty MIME type is outside the schema.
    Rules: normalize_public_sign R2."""
    # Then 1
    with pytest.raises(ValidationError):
        M.normalize_public_sign(file_name="photo.jpg", mime_type="", file_size=10)


# =========================================================================== #
# sign_staging_upload
# =========================================================================== #

def test_mobs_sg_01__accepted_request_stages_minted_id(db, R, CL):
    """MOBS-SG-01 — an accepted request stages a server-minted id on the session.
    Rules: sign_staging_upload R4, R5."""
    S = add(db, sess(R))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 1
    assert result.public_id == "development/ws-" + str(R.W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id == "development/ws-" + str(R.W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN
    # Then 3
    assert row.asset_folder == "Dev/" + R.W1.name + "/Mobile Staging/session-" + str(S.id)
    # Then 4
    assert row.resource_type == "image"
    assert row.file_name == "photo.jpg"
    assert row.mime_type == "image/jpeg"
    assert row.file_size == 1234
    assert row.status == "waiting"
    # Then 5
    assert CL.dr.called is False
    assert CL.gr.called is False
    assert CL.rr.called is False


def test_mobs_sg_02__response_fields(db, R):
    """MOBS-SG-02 — the response holds every field as stated.
    Rules: sign_staging_upload R7."""
    S = add(db, sess(R))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 1
    assert result.cloud_name == "demo-cloud"
    assert result.api_key == "123456"
    assert result.timestamp == 1767225600
    # Then 2
    assert result.asset_folder == "Dev/" + R.W1.name + "/Mobile Staging/session-" + str(S.id)
    assert result.display_name == "photo.jpg"
    # Then 3
    assert result.type == "authenticated"
    assert result.signature == "sig-x"
    assert result.resource_type == "image"
    # Then 4
    assert result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"


def test_mobs_sg_03__signer_gets_response_values(db, R, CL):
    """MOBS-SG-03 — the signer receives the response's own values.
    Rules: sign_staging_upload R7."""
    S = add(db, sess(R))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 1
    assert result.signature == "sig-x"
    # Then 2
    CL.gus.assert_called_once()
    assert kw(CL.gus)["public_id"] == result.public_id
    assert kw(CL.gus)["asset_folder"] == result.asset_folder
    assert kw(CL.gus)["display_name"] == "photo.jpg"
    # Then 3
    assert kw(CL.gus)["timestamp"] == 1767225600
    assert kw(CL.gus)["delivery_type"] == "authenticated"


def test_mobs_sg_04__document_staged_as_raw(db, R):
    """MOBS-SG-04 — a document is staged as raw with a raw upload URL.
    Rules: sign_staging_upload R4, R7."""
    S = add(db, sess(R))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="notes.docx", mime_type=DOCX, file_size=50)
    # Then 1
    assert result.resource_type == "raw"
    assert result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/raw/upload"
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.resource_type == "raw"
    assert row.file_name == "notes.docx"


def test_mobs_sg_05__name_sanitized_mime_as_sent(db, R):
    """MOBS-SG-05 — the file name is stored sanitized, the MIME type as sent.
    Rules: sign_staging_upload R4."""
    S = add(db, sess(R))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="  my/scan.pdf ", mime_type="application/pdf", file_size=77)
    # Then 1
    assert result.display_name == "my-scan.pdf"
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.file_name == "my-scan.pdf"
    assert row.mime_type == "application/pdf"
    assert row.file_size == 77
    assert row.resource_type == "image"


def test_mobs_sg_06__uploaded_refuses_sign(db, R, CL):
    """MOBS-SG-06 — an uploaded session refuses a new sign.
    Rules: sign_staging_upload R1."""
    S = add(db, sess(R, "uploaded"))
    before = snap(db, S)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before)


def test_mobs_sg_07__consumed_refuses_sign(db, R, CL):
    """MOBS-SG-07 — a consumed session refuses a sign.
    Rules: sign_staging_upload R1."""
    S = add(db, sess(R, status="consumed"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []


def test_mobs_sg_08__cancelled_refuses_sign(db, R, CL):
    """MOBS-SG-08 — a cancelled session refuses a sign.
    Rules: sign_staging_upload R1."""
    S = add(db, sess(R, "staged", status="cancelled"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert reread(db, MobileUploadSession, S.id).public_id == STG


def test_mobs_sg_09__expired_refuses_sign(db, R, CL):
    """MOBS-SG-09 — an expired session refuses a sign.
    Rules: sign_staging_upload R1."""
    S = add(db, sess(R, status="expired"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []


def test_mobs_sg_10__resign_deletes_earlier_file(db, R, CL):
    """MOBS-SG-10 — a re-sign deletes the earlier staged file and replaces its id.
    Rules: sign_staging_upload R2."""
    S = add(db, sess(R, "staged", public_id=OLD, resource_type="raw", delivery_type="authenticated", file_name="notes.docx"))
    result = M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 1
    assert result.public_id == "development/ws-" + str(R.W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN
    # Then 2
    CL.dr.assert_called_once()
    assert kw(CL.dr)["public_id"] == OLD
    assert kw(CL.dr)["resource_type"] == "raw"
    assert kw(CL.dr)["delivery_type"] == "authenticated"
    # Then 3
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id == "development/ws-" + str(R.W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN
    assert row.resource_type == "image"
    assert row.file_name == "photo.jpg"


def test_mobs_sg_11__refused_request_stages_nothing(db, R, CL):
    """MOBS-SG-11 — a refused request with no earlier file stages nothing.
    Rules: sign_staging_upload R3, (Errors: invalid file)."""
    S = add(db, sess(R))
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.png", mime_type="image/jpeg", file_size=10)
    # Then 2
    assert str(exc.value) == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."
    # Then 3
    assert cl_called(CL) == []
    # Then 4
    assert S.public_id is None


@XF2140
def test_mobs_sg_12__refused_resign_keeps_earlier_mime(db, R, CL):
    """MOBS-SG-12 — a refused re-sign keeps the earlier file (MIME mismatch).
    Rules: sign_staging_upload R3 [BUG-2140]."""
    S = add(db, sess(R, "staged", public_id=OLD, asset_folder="Dev/x/Mobile Staging/session-0"))
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="notes.docx", mime_type="application/pdf", file_size=10)
    # Then 2
    assert str(exc.value).startswith("MIME type 'application/pdf' does not match .docx")
    # Then 3
    assert CL.dr.called is False
    # Then 4
    assert S.public_id == OLD
    assert S.asset_folder == "Dev/x/Mobile Staging/session-0"
    # Then 5
    assert cl_called(CL) == []


@XF2140
def test_mobs_sg_13__refused_resign_keeps_earlier_too_large(db, R, CL):
    """MOBS-SG-13 — a refused re-sign keeps the earlier file (too large).
    Rules: sign_staging_upload R3 [BUG-2140]."""
    S = add(db, sess(R, "staged", public_id=OLD))
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=10485761)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."
    # Then 3
    assert CL.dr.called is False
    # Then 4
    assert S.public_id == OLD


def test_mobs_sg_14__empty_cloud_name_after_flush(db, R, CL):
    """MOBS-SG-14 — an empty cloud name refuses after the flush, without signing.
    Rules: sign_staging_upload R6."""
    CL.setting("CLOUDINARY_CLOUD_NAME", "")
    S = add(db, sess(R))
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert CL.gus.called is False
    # Then 4
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id == "development/ws-" + str(R.W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN
    assert row.file_name == "photo.jpg"


def test_mobs_sg_15__empty_api_key_refuses(db, R, CL):
    """MOBS-SG-15 — an empty API key refuses the same way.
    Rules: sign_staging_upload R6."""
    CL.setting("CLOUDINARY_API_KEY", "")
    S = add(db, sess(R))
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert CL.gus.called is False


# [claude] MOBS-SG-16
def test_mobs_sg_16__empty_secret_raises_from_real_signer(db, R, CL):
    """MOBS-SG-16 — an empty secret raises from the real signer.
    Rules: sign_staging_upload R6."""
    CL.setting("CLOUDINARY_API_SECRET", "")
    CL.real("gus")
    S = add(db, sess(R))
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError):
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)


def test_mobs_sg_17__flushes_never_commits(db, R):
    """MOBS-SG-17 — sign flushes and never commits.
    Rules: sign_staging_upload (Side effects)."""
    S = add(db, sess(R))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.sign_staging_upload(db, session=S, workspace=R.W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, MobileUploadSession, S.id).public_id is None


# =========================================================================== #
# confirm_staging_upload
# =========================================================================== #

def test_mobs_cf_01__verified_file_uploaded(db, R, CL):
    """MOBS-CF-01 — a verified file makes the session uploaded.
    Rules: confirm_staging_upload R6."""
    S = add(db, sess(R, "staged"))
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "uploaded"
    assert row.format == "jpg"
    assert row.version == 1700000000
    assert row.file_size == 2048
    assert row.mime_type == "image/jpeg"
    assert row.public_id == STG
    # Then 3
    assert CL.dr.called is False


def test_mobs_cf_02__asks_about_own_id_and_types(db, R, CL):
    """MOBS-CF-02 — Cloudinary is asked about the session's own id and types.
    Rules: confirm_staging_upload R2."""
    S = add(db, sess(R, "staged", resource_type="image", delivery_type="authenticated"))
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result.status == "uploaded"
    # Then 2
    CL.gr.assert_called_once()
    assert kw(CL.gr)["public_id"] == STG
    assert kw(CL.gr)["resource_type"] == "image"
    assert kw(CL.gr)["delivery_type"] == "authenticated"


def test_mobs_cf_03__missing_types_default_in_lookup(db, R, CL):
    """MOBS-CF-03 — missing types default to image / authenticated in the lookup.
    Rules: confirm_staging_upload R2."""
    S = add(db, sess(R, "staged", resource_type=None, delivery_type=None))
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result.status == "uploaded"
    # Then 2
    assert kw(CL.gr)["resource_type"] == "image"
    assert kw(CL.gr)["delivery_type"] == "authenticated"


def test_mobs_cf_04__raw_document_keeps_type_and_mime(db, R, CL):
    """MOBS-CF-04 — a raw document keeps its stored type and MIME.
    Rules: confirm_staging_upload R2, R6."""
    S = add(db, sess(R, "staged", resource_type="raw", file_name="notes.docx", mime_type=DOCX))
    CL.gr.return_value = {"resource_type": "raw", "format": "docx", "bytes": 900, "version": 1700000002}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert kw(CL.gr)["resource_type"] == "raw"
    # Then 3
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "uploaded"
    assert row.format == "docx"
    assert row.file_size == 900
    assert row.mime_type == DOCX


def test_mobs_cf_05__bytes_zero_keeps_declared_size(db, R, CL):
    """MOBS-CF-05 — bytes 0 keeps the declared size.
    Rules: confirm_staging_upload R6."""
    S = add(db, sess(R, "staged", file_size=1234))
    CL.gr.return_value = {**GR, "bytes": 0}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.file_size == 1234
    assert row.status == "uploaded"


def test_mobs_cf_06__no_bytes_key_keeps_declared_size(db, R, CL):
    """MOBS-CF-06 — no bytes key keeps the declared size.
    Rules: confirm_staging_upload R6."""
    S = add(db, sess(R, "staged", file_size=1234))
    CL.gr.return_value = {"resource_type": "image", "format": "jpg", "version": 1700000000}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert reread(db, MobileUploadSession, S.id).file_size == 1234


def test_mobs_cf_07__image_pdf_sets_pdf_mime(db, R, CL):
    """MOBS-CF-07 — Cloudinary image + pdf sets the PDF MIME type.
    Rules: confirm_staging_upload R6."""
    S = add(db, sess(R, "staged", file_name="scan.pdf", mime_type="application/octet-stream"))
    CL.gr.return_value = {**GR, "format": "pdf"}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.mime_type == "application/pdf"
    assert row.format == "pdf"
    assert row.status == "uploaded"


def test_mobs_cf_08__capital_jpg_format_accepted(db, R, CL):
    """MOBS-CF-08 — format "JPG" in capitals is accepted.
    Rules: confirm_staging_upload R4."""
    S = add(db, sess(R, "staged"))
    CL.gr.return_value = {**GR, "format": "JPG"}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result.status == "uploaded"


def test_mobs_cf_09__max_bytes_passes(db, R, CL):
    """MOBS-CF-09 — exactly 10 485 760 bytes passes.
    Rules: confirm_staging_upload R5."""
    S = add(db, sess(R, "staged"))
    CL.gr.return_value = {**GR, "bytes": 10485760}
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "uploaded"
    assert row.file_size == 10485760
    assert row.public_id == STG
    # Then 3
    assert CL.dr.called is False


def test_mobs_cf_10__over_max_deletes_and_clears(db, R, CL):
    """MOBS-CF-10 — 10 485 761 bytes deletes the file and clears the session.
    Rules: confirm_staging_upload R5 (BUG-2137, manager part)."""
    S = add(db, sess(R, "staged"))
    CL.gr.return_value = {**GR, "bytes": 10485761}
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."
    # Then 3
    CL.dr.assert_called_once()
    assert kw(CL.dr)["public_id"] == STG
    assert kw(CL.dr)["resource_type"] == "image"
    assert kw(CL.dr)["delivery_type"] == "authenticated"
    # Then 4
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id is None
    assert row.asset_folder is None
    assert row.status == "waiting"


def test_mobs_cf_11__uploaded_refuses_second_confirm(db, R, CL):
    """MOBS-CF-11 — an uploaded session refuses a second confirm.
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "uploaded"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []


def test_mobs_cf_12__consumed_refuses_confirm(db, R, CL):
    """MOBS-CF-12 — a consumed session refuses a confirm.
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", status="consumed"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []


def test_mobs_cf_13__cancelled_refuses_confirm(db, R, CL):
    """MOBS-CF-13 — a cancelled session refuses a confirm.
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", status="cancelled"))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "This session already received a file."
    # Then 3
    assert cl_called(CL) == []


def test_mobs_cf_14__no_public_id_not_prepared(db, R, CL):
    """MOBS-CF-14 — no public_id: "Upload was not prepared."
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", public_id=None))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Upload was not prepared."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []


def test_mobs_cf_15__empty_public_id_not_prepared(db, R, CL):
    """MOBS-CF-15 — an empty public_id: "Upload was not prepared."
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", public_id=""))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Upload was not prepared."
    # Then 3
    assert cl_called(CL) == []


def test_mobs_cf_16__no_file_name_not_prepared(db, R, CL):
    """MOBS-CF-16 — no file name: "Upload was not prepared."
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", file_name=None))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Upload was not prepared."
    # Then 3
    assert cl_called(CL) == []


def test_mobs_cf_17__empty_file_name_not_prepared(db, R, CL):
    """MOBS-CF-17 — an empty file name: "Upload was not prepared."
    Rules: confirm_staging_upload R1."""
    S = add(db, sess(R, "staged", file_name=""))
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Upload was not prepared."
    # Then 3
    assert cl_called(CL) == []


def test_mobs_cf_18__lookup_error_leaves_waiting(db, R, CL):
    """MOBS-CF-18 — a lookup error leaves the session waiting.
    Rules: confirm_staging_upload R3."""
    S = add(db, sess(R, "staged"))
    CL.gr.side_effect = RuntimeError("boom")
    before = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    assert not db.dirty
    # Then 4
    assert CL.dr.called is False
    # Then 5
    assert unchanged(db, S, before)


@XF2141
def test_mobs_cf_19__not_configured_passes_through(db, R, CL):
    """MOBS-CF-19 — "not configured" during the lookup passes through.
    Rules: confirm_staging_upload R3 [BUG-2141]."""
    S = add(db, sess(R, "staged"))
    CL.gr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    before = snap(db, S)
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Cloudinary is not configured."
    # Then 3
    assert not db.dirty
    # Then 4
    assert unchanged(db, S, before)


def test_mobs_cf_20__wrong_resource_type_refused(db, R, CL):
    """MOBS-CF-20 — a resource of the wrong type is refused, the session unchanged.
    Rules: confirm_staging_upload R4."""
    S = add(db, sess(R, "staged"))
    CL.gr.return_value = {**GR, "resource_type": "raw"}
    before = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Cloudinary resource_type 'raw' does not match .jpg (expected 'image')."
    # Then 3
    assert not db.dirty
    # Then 4
    assert CL.dr.called is False
    # Then 5
    assert unchanged(db, S, before)


def test_mobs_cf_21__wrong_format_refused(db, R, CL):
    """MOBS-CF-21 — a resource of the wrong format is refused.
    Rules: confirm_staging_upload R4."""
    S = add(db, sess(R, "staged"))
    CL.gr.return_value = {**GR, "format": "png"}
    before = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.confirm_staging_upload(db, session=S)
    # Then 2
    assert str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."
    # Then 3
    assert not db.dirty
    # Then 4
    assert unchanged(db, S, before)


def test_mobs_cf_22__flushes_never_commits(db, R):
    """MOBS-CF-22 — confirm flushes and never commits.
    Rules: confirm_staging_upload (Side effects)."""
    S = add(db, sess(R, "staged"))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.confirm_staging_upload(db, session=S)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "waiting"


def test_mobs_cf_23__stored_delivery_type_used_for_lookup(db, R, CL):
    """MOBS-CF-23 — a stored non-default delivery type is used for the lookup.
    Rules: confirm_staging_upload R2."""
    S = add(db, sess(R, "staged", delivery_type="upload"))
    result = M.confirm_staging_upload(db, session=S)
    # Then 1
    assert result.status == "uploaded"
    # Then 2
    CL.gr.assert_called_once()
    assert kw(CL.gr)["public_id"] == STG
    assert kw(CL.gr)["delivery_type"] == "upload"
    assert kw(CL.gr)["resource_type"] == "image"


# =========================================================================== #
# _destroy_staging_asset
# =========================================================================== #

def test_mobs_ds_01__own_id_deleted_session_unchanged(db, R, CL):
    """MOBS-DS-01 — the session's own id is deleted with its types; the session is not changed.
    Rules: _destroy_staging_asset R1."""
    S = add(db, sess(R, "staged", resource_type="raw", delivery_type="authenticated"))
    M._destroy_staging_asset(S)
    # Then 1
    CL.dr.assert_called_once()
    assert kw(CL.dr)["public_id"] == STG
    assert kw(CL.dr)["resource_type"] == "raw"
    assert kw(CL.dr)["delivery_type"] == "authenticated"
    # Then 2
    assert not db.dirty
    # Then 3
    assert S.public_id == STG


def test_mobs_ds_02__missing_types_default(db, R, CL):
    """MOBS-DS-02 — missing types default to image / authenticated.
    Rules: _destroy_staging_asset R1."""
    S = add(db, sess(R, "staged", resource_type=None, delivery_type=None))
    S.delivery_type = None  # NOT NULL column: the flush stored its default; the card's None is kept in memory
    M._destroy_staging_asset(S)
    # Then 1
    assert kw(CL.dr)["resource_type"] == "image"
    assert kw(CL.dr)["delivery_type"] == "authenticated"


def test_mobs_ds_03__no_public_id_no_call(db, R, CL):
    """MOBS-DS-03 — no public_id: no call.
    Rules: _destroy_staging_asset R2."""
    S = add(db, sess(R))
    M._destroy_staging_asset(S)
    # Then 1
    assert CL.dr.called is False


def test_mobs_ds_04__empty_public_id_no_call(db, R, CL):
    """MOBS-DS-04 — an empty public_id: no call.
    Rules: _destroy_staging_asset R2."""
    S = add(db, sess(R, "staged", public_id=""))
    M._destroy_staging_asset(S)
    # Then 1
    assert CL.dr.called is False


def test_mobs_ds_05__delete_error_swallowed(db, R, CL):
    """MOBS-DS-05 — a delete error is swallowed.
    Rules: _destroy_staging_asset R3."""
    S = add(db, sess(R, "staged"))
    CL.dr.side_effect = RuntimeError("down")
    M._destroy_staging_asset(S)  # no error expected
    # Then 1
    CL.dr.assert_called_once()
    # Then 2
    assert not db.dirty


def test_mobs_ds_06__not_configured_swallowed(db, R, CL):
    """MOBS-DS-06 — "not configured" is swallowed too.
    Rules: _destroy_staging_asset R3."""
    S = add(db, sess(R, "staged"))
    CL.dr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    M._destroy_staging_asset(S)  # no error expected
    # Then 1
    CL.dr.assert_called_once()


@XF2136
def test_mobs_ds_07__failed_delete_logs_warning(db, R, CL, warnings_log):
    """MOBS-DS-07 — a failed delete logs a WARNING naming the id and the error.
    Rules: _destroy_staging_asset R3 [BUG-2136]."""
    S = add(db, sess(R, "staged"))
    CL.dr.side_effect = RuntimeError("down")
    M._destroy_staging_asset(S)
    # Then 1
    CL.dr.assert_called_once()
    # Then 2
    records = warnings_log()
    assert len(records) == 1
    assert STG in records[0].getMessage()
    assert "down" in records[0].getMessage()


# =========================================================================== #
# cancel_session
# =========================================================================== #

def test_mobs_cn_01__consumed_returned_untouched(db, R, CL):
    """MOBS-CN-01 — a consumed session is returned untouched.
    Rules: cancel_session R1."""
    S = add(db, sess(R, "staged", status="consumed"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert not db.dirty
    # Then 3
    assert cl_called(CL) == []
    # Then 4
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "consumed"
    assert row.public_id == STG


def test_mobs_cn_02__waiting_without_file_cancelled(db, R, CL):
    """MOBS-CN-02 — a waiting session with no file ends cancelled.
    Rules: cancel_session R2."""
    S = add(db, sess(R))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "cancelled"
    # Then 3
    assert CL.dr.called is False


def test_mobs_cn_03__cancelled_cancelled_again(db, R):
    """MOBS-CN-03 — a cancelled session is cancelled again without error.
    Rules: cancel_session R2."""
    S = add(db, sess(R, status="cancelled"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "cancelled"


def test_mobs_cn_04__expired_cancelled(db, R):
    """MOBS-CN-04 — an expired session ends cancelled.
    Rules: cancel_session R2."""
    S = add(db, sess(R, status="expired"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "cancelled"


def test_mobs_cn_05__uploaded_file_deleted(db, R, CL):
    """MOBS-CN-05 — an uploaded session's staged file is deleted.
    Rules: cancel_session R3."""
    S = add(db, sess(R, "uploaded"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    CL.dr.assert_called_once()
    assert kw(CL.dr)["public_id"] == STG
    # Then 3
    assert reread(db, MobileUploadSession, S.id).status == "cancelled"


@XF2138
def test_mobs_cn_06__uploaded_cancel_clears_id(db, R, CL):
    """MOBS-CN-06 — cancelling an uploaded session clears its staged id.
    Rules: cancel_session R4 [BUG-2138]."""
    S = add(db, sess(R, "uploaded"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    CL.dr.assert_called_once()
    # Then 3
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id is None
    assert row.asset_folder is None
    assert row.status == "cancelled"


@XF2138
def test_mobs_cn_07__waiting_cancel_deletes_signed_file(db, R, CL):
    """MOBS-CN-07 — cancelling a waiting session deletes its signed file.
    Rules: cancel_session R4 [BUG-2138]."""
    S = add(db, sess(R, "staged"))
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    CL.dr.assert_called_once()
    assert kw(CL.dr)["public_id"] == STG
    # Then 3
    row = reread(db, MobileUploadSession, S.id)
    assert row.public_id is None
    assert row.asset_folder is None
    assert row.status == "cancelled"


def test_mobs_cn_08__failed_delete_does_not_stop_cancel(db, R, CL):
    """MOBS-CN-08 — a failed delete does not stop the cancel.
    Rules: cancel_session R5."""
    S = add(db, sess(R, "uploaded"))
    CL.dr.side_effect = RuntimeError("down")
    result = M.cancel_session(db, session=S)
    # Then 1
    assert result is S
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "cancelled"


def test_mobs_cn_09__flushes_never_commits(db, R):
    """MOBS-CN-09 — cancel flushes and never commits.
    Rules: cancel_session (Side effects)."""
    S = add(db, sess(R))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.cancel_session(db, session=S)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "waiting"


# =========================================================================== #
# _promote_file_name
# =========================================================================== #

def test_mobs_pf_01__no_new_name_keeps_staged(R):
    """MOBS-PF-01 — no new name keeps the staged name.
    Rules: _promote_file_name R1."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, None)
    # Then 1
    assert result == "photo.JPG"


def test_mobs_pf_02__empty_new_name_keeps_staged(R):
    """MOBS-PF-02 — an empty new name keeps the staged name.
    Rules: _promote_file_name R1."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "")
    # Then 1
    assert result == "photo.JPG"


def test_mobs_pf_03__whitespace_new_name_keeps_staged(R):
    """MOBS-PF-03 — a whitespace-only new name keeps the staged name.
    Rules: _promote_file_name R1."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "  \t ")
    # Then 1
    assert result == "photo.JPG"


def test_mobs_pf_04__no_staged_name_upload_jpg(R):
    """MOBS-PF-04 — no staged name gives "upload.jpg".
    Rules: _promote_file_name R1."""
    S = sess(R, "uploaded", file_name=None)
    result = M._promote_file_name(S, None)
    # Then 1
    assert result == "upload.jpg"


def test_mobs_pf_05__new_extension_replaced_case_kept(R):
    """MOBS-PF-05 — the new name's extension is replaced by the staged one, case kept.
    Rules: _promote_file_name R2, R3."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "x.png")
    # Then 1
    assert result == "x.JPG"


def test_mobs_pf_06__staged_without_dot_gives_jpg(R):
    """MOBS-PF-06 — a staged name with no dot gives "jpg".
    Rules: _promote_file_name R2."""
    S = sess(R, "uploaded", file_name="README")
    result = M._promote_file_name(S, "new")
    # Then 1
    assert result == "new.jpg"


def test_mobs_pf_07__only_last_dot_dropped(R):
    """MOBS-PF-07 — only the last dot of the new name is dropped.
    Rules: _promote_file_name R3."""
    S = sess(R, "uploaded", file_name="scan.v2.pdf")
    result = M._promote_file_name(S, "a.b.c")
    # Then 1
    assert result == "a.b.pdf"


def test_mobs_pf_08__new_name_trimmed_and_sanitized(R):
    """MOBS-PF-08 — the new name is trimmed and sanitized.
    Rules: _promote_file_name R3."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "  dir/na<me> Q ")
    # Then 1
    assert result == "dir-name Q.JPG"


def test_mobs_pf_09__base_251_gives_255(R):
    """MOBS-PF-09 — a base of exactly 251 characters gives 255 with the extension.
    Rules: _promote_file_name R5."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "a" * 251)
    # Then 1
    assert result == "a" * 251 + ".JPG"


@XF2135
def test_mobs_pf_10__longer_base_shortened_extension_survives(R):
    """MOBS-PF-10 — a longer base is shortened so the extension survives.
    Rules: _promote_file_name R5 [BUG-2135]."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "a" * 252)
    # Then 1
    assert result == "a" * 251 + ".JPG"


@XF2135
def test_mobs_pf_11__dot_gives_staged_name(R):
    """MOBS-PF-11 — "." gives the staged name.
    Rules: _promote_file_name R6 [BUG-2135]."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, ".")
    # Then 1
    assert result == "photo.JPG"


@XF2135
def test_mobs_pf_12__space_dot_x_gives_staged_name(R):
    """MOBS-PF-12 — "  .x" gives the staged name.
    Rules: _promote_file_name R6 [BUG-2135]."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "  .x")
    # Then 1
    assert result == "photo.JPG"


@XF2135
def test_mobs_pf_13__base_cleaning_to_nothing_gives_staged(R):
    """MOBS-PF-13 — a base that cleans to nothing ("<>") gives the staged name.
    Rules: _promote_file_name R6 [BUG-2135]."""
    S = sess(R, "uploaded", file_name="photo.JPG")
    result = M._promote_file_name(S, "<>")
    # Then 1
    assert result == "photo.JPG"


@XF2135
def test_mobs_pf_14__dot_ending_staged_and_empty_name(R):
    """MOBS-PF-14 — a staged name ending in "." with a name that cleans to nothing gives the staged name.
    Rules: _promote_file_name R4, R6 [BUG-2135]."""
    S = sess(R, "uploaded", file_name="photo.")
    # Then 1 (the call itself raises AttachmentValidationError "Invalid file name." today)
    result = M._promote_file_name(S, "?")
    assert result == "photo."


# =========================================================================== #
# promote_to_attachment
# =========================================================================== #

def test_mobs_pm_01__staged_file_becomes_ready_attachment(db, R):
    """MOBS-PM-01 — a staged file becomes a ready attachment and the session is consumed.
    Rules: promote_to_attachment R9, R10, R11."""
    S = add(db, sess(R, "uploaded", entity_label="Phone label"))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note="Receipt")
    # Then 1
    assert result.upload_status == "ready"
    assert result.public_id == DEST(R)
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "consumed"
    assert row.public_id is None
    # Then 3
    assert row.asset_folder == "Dev/" + R.W1.name + "/Projects/Tender"
    # Then 4
    att = reread(db, Attachment, result.id)
    assert att.file_name == "photo.jpg"
    assert att.mime_type == "image/jpeg"
    assert att.uploaded_by == R.UG.id
    assert att.note == "Receipt"
    assert att.file_size == 2048
    assert att.asset_folder == "Dev/" + R.W1.name + "/Projects/Tender"
    # Then 5
    assert count(
        db, "attachment_links", "attachment_id = :a AND entity_type = 'project' AND entity_id = :e",
        a=att.id, e=R.P1.id,
    ) == 1


def test_mobs_pm_02__moved_to_server_minted_id(db, R, CL):
    """MOBS-PM-02 — the file is moved from the staged id to a server-minted id.
    Rules: promote_to_attachment R7, R9."""
    S = add(db, sess(R, "uploaded"))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.public_id == DEST(R)
    # Then 2
    CL.rr.assert_called_once()
    assert kw(CL.rr)["from_public_id"] == STG
    assert kw(CL.rr)["to_public_id"] == DEST(R)
    assert kw(CL.rr)["resource_type"] == "image"
    assert kw(CL.rr)["delivery_type"] == "authenticated"
    # Then 3
    CL.um.assert_called_once()
    assert kw(CL.um)["public_id"] == DEST(R)
    assert kw(CL.um)["asset_folder"] == "Dev/" + R.W1.name + "/Projects/Tender"
    assert kw(CL.um)["display_name"] == "photo.jpg"
    # Then 4
    CL.agr.assert_called_once()
    assert kw(CL.agr)["public_id"] == DEST(R)
    # Then 5
    assert CL.dr.called is False
    assert CL.adr.called is False


def test_mobs_pm_03__missing_types_fall_back(db, R, CL):
    """MOBS-PM-03 — missing types fall back to the normalized type and authenticated.
    Rules: promote_to_attachment R7."""
    S = add(db, sess(R, "uploaded", resource_type=None, delivery_type=None))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert kw(CL.rr)["resource_type"] == "image"
    assert kw(CL.rr)["delivery_type"] == "authenticated"


def test_mobs_pm_04__raw_document_moved_as_raw(db, R, CL):
    """MOBS-PM-04 — a raw document is moved as raw.
    Rules: promote_to_attachment R7."""
    S = add(db, sess(R, "uploaded", resource_type="raw", file_name="notes.docx", mime_type=DOCX, format="docx"))
    CL.agr.return_value = {**GRA, "resource_type": "raw", "format": "docx"}
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.file_name == "notes.docx"
    # Then 2
    assert kw(CL.rr)["resource_type"] == "raw"


def test_mobs_pm_05__ledger_and_activity(db, R):
    """MOBS-PM-05 — ledger and activity: pending + ready by the caller, "Attached …" on the project.
    Rules: promote_to_attachment R10."""
    S = add(db, sess(R, "uploaded"))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert count(
        db, "attachment_ledger", "attachment_id = :a AND transaction_type = 'pending' AND performed_by = :u",
        a=result.id, u=R.UG.id,
    ) == 1
    # Then 3
    assert count(
        db, "attachment_ledger", "attachment_id = :a AND transaction_type = 'ready' AND performed_by = :u",
        a=result.id, u=R.UG.id,
    ) == 1
    # Then 4
    assert count(
        db, "project_events",
        "project_id = :p AND event_type = 'attachment_added' AND description = 'Attached photo.jpg' AND performed_by = :u",
        p=R.P1.id, u=R.UG.id,
    ) == 1


def test_mobs_pm_06__new_name_keeps_staged_extension(db, R, CL):
    """MOBS-PM-06 — a new name keeps the staged extension.
    Rules: promote_to_attachment R6."""
    S = add(db, sess(R, "uploaded"))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name="Invoice 7.png", note=None)
    # Then 1
    assert result.file_name == "Invoice 7.jpg"
    # Then 2
    assert kw(CL.um)["display_name"] == "Invoice 7.jpg"


def test_mobs_pm_07__missing_size_sent_as_one(db, R, CL):
    """MOBS-PM-07 — a missing size is sent as 1.
    Rules: promote_to_attachment R3, R6."""
    S = add(db, sess(R, "uploaded", file_size=None))
    CL.agr.return_value = {**GRA, "bytes": 0}
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, Attachment, result.id).file_size == 1


def test_mobs_pm_08__max_stored_bytes_passes(db, R, CL):
    """MOBS-PM-08 — exactly 10 485 760 stored bytes passes.
    Rules: promote_to_attachment R3."""
    S = add(db, sess(R, "uploaded", file_size=10485760))
    CL.agr.return_value = {**GRA, "bytes": 10485760}
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_09__over_max_refused_before_any_call(db, R, CL):
    """MOBS-PM-09 — 10 485 761 stored bytes is refused before any call.
    Rules: promote_to_attachment R3."""
    S = add(db, sess(R, "uploaded", file_size=10485761))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert counts(db) == before


def test_mobs_pm_10__waiting_has_no_file(db, R, CL):
    """MOBS-PM-10 — a waiting session has no file to attach.
    Rules: promote_to_attachment R1."""
    S = add(db, sess(R, "staged"))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "No file is ready on this session."
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert counts(db) == before


def test_mobs_pm_11__consumed_refuses_second_promote(db, R, CL):
    """MOBS-PM-11 — a consumed session refuses a second promote.
    Rules: promote_to_attachment R1."""
    S = add(db, sess(R, "uploaded", status="consumed", public_id=None))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "No file is ready on this session."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert counts(db) == before


def test_mobs_pm_12__cancelled_refuses_promote(db, R, CL):
    """MOBS-PM-12 — a cancelled session refuses a promote.
    Rules: promote_to_attachment R1."""
    S = add(db, sess(R, "uploaded", status="cancelled"))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "No file is ready on this session."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert counts(db) == before


def test_mobs_pm_13__expired_refuses_promote(db, R, CL):
    """MOBS-PM-13 — an expired session refuses a promote.
    Rules: promote_to_attachment R1."""
    S = add(db, sess(R, "uploaded", status="expired"))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "No file is ready on this session."
    # Then 3
    assert cl_called(CL) == []
    # Then 4
    assert counts(db) == before


def test_mobs_pm_14__no_public_id_incomplete(db, R, CL):
    """MOBS-PM-14 — no public_id: staging metadata is incomplete.
    Rules: promote_to_attachment R2."""
    S = add(db, sess(R, "uploaded", public_id=None))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "Staging metadata is incomplete."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert counts(db) == before


def test_mobs_pm_15__no_file_name_incomplete(db, R, CL):
    """MOBS-PM-15 — no file name: staging metadata is incomplete.
    Rules: promote_to_attachment R2."""
    S = add(db, sess(R, "uploaded", file_name=""))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "Staging metadata is incomplete."
    # Then 3
    assert cl_called(CL) == []
    # Then 4
    assert counts(db) == before


def test_mobs_pm_16__no_mime_incomplete(db, R, CL):
    """MOBS-PM-16 — no MIME type: staging metadata is incomplete.
    Rules: promote_to_attachment R2."""
    S = add(db, sess(R, "uploaded", mime_type=None))
    before = counts(db)
    # Then 1
    with pytest.raises(MobileUploadSessionError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "Staging metadata is incomplete."
    # Then 3
    assert cl_called(CL) == []
    # Then 4
    assert counts(db) == before


def test_mobs_pm_17__mime_mismatch_refused_before_move(db, R, CL):
    """MOBS-PM-17 — a MIME type that no longer matches is refused before the move.
    Rules: promote_to_attachment R5, R6 (name / type)."""
    S = add(db, sess(R, "uploaded", mime_type="image/png"))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "MIME type 'image/png' does not match .jpg (expected one of: image/jpeg)."
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert counts(db) == before


def test_mobs_pm_18__full_record_refused(db, R):
    """MOBS-PM-18 — a full record is refused (the error itself).
    Rules: promote_to_attachment (Errors: record full)."""
    full(db, R, R.P1)
    S = add(db, sess(R, "uploaded"))
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."


@XF2133
def test_mobs_pm_19__full_record_refused_before_move(db, R, CL):
    """MOBS-PM-19 — a full record is refused before the file is moved.
    Rules: promote_to_attachment R5 [BUG-2133]."""
    full(db, R, R.P1)
    S = add(db, sess(R, "uploaded"))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."
    # Then 3
    assert CL.rr.called is False
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert not db.dirty
    # Then 6
    assert not db.new
    # Then 7
    assert unchanged(db, S, before_s)


def test_mobs_pm_20__failed_move_leaves_session(db, R, CL):
    """MOBS-PM-20 — a failed move leaves the session as it was.
    Rules: promote_to_attachment R8."""
    S = add(db, sess(R, "uploaded"))
    CL.rr.side_effect = RuntimeError("gone")
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "Cloudinary move failed: gone"
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert CL.um.called is False
    assert CL.agr.called is False
    # Then 6
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "uploaded"
    assert row.public_id == STG


@XF2141
def test_mobs_pm_21__not_configured_move_passes_through(db, R, CL):
    """MOBS-PM-21 — "not configured" during the move passes through.
    Rules: promote_to_attachment R8 [BUG-2141]."""
    S = add(db, sess(R, "uploaded"))
    CL.rr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError):
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert not db.dirty
    # Then 3
    assert not db.new
    # Then 4
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "uploaded"
    assert row.public_id == STG


def test_mobs_pm_22__failed_metadata_does_not_stop(db, R, CL):
    """MOBS-PM-22 — a failed metadata update does not stop the promote.
    Rules: promote_to_attachment R9."""
    S = add(db, sess(R, "uploaded"))
    CL.um.side_effect = RuntimeError("meta")
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


@XF2136
def test_mobs_pm_23__failed_metadata_logs_warning(db, R, CL, warnings_log):
    """MOBS-PM-23 — a failed metadata update logs a WARNING naming the new id.
    Rules: promote_to_attachment R9 [BUG-2136]."""
    S = add(db, sess(R, "uploaded"))
    CL.um.side_effect = RuntimeError("meta")
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    records = warnings_log()
    assert len(records) == 1
    assert DEST(R) in records[0].getMessage()
    assert "meta" in records[0].getMessage()


def test_mobs_pm_24__confirm_refusal_raised_as_is(db, R, CL):
    """MOBS-PM-24 — a confirm refusal of the moved file is raised as it is.
    Rules: promote_to_attachment R10 (Errors: confirm fails)."""
    S = add(db, sess(R, "uploaded"))
    CL.agr.return_value = {**GRA, "format": "png"}
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."


def test_mobs_pm_25__flushes_never_commits(db, R):
    """MOBS-PM-25 — promote flushes and never commits.
    Rules: promote_to_attachment (Side effects)."""
    S = add(db, sess(R, "uploaded"))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "uploaded"


@XF2134
def test_mobs_pm_26__deleted_project_refused(db, R, CL):
    """MOBS-PM-26 — PR-1: the session's project was deleted since.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    PD = proj(db, R, "Old Job", deleted=True)
    S = add(db, sess(R, "uploaded", entity_id=PD.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PD.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_27__unknown_project_refused(db, R, CL):
    """MOBS-PM-27 — PR-1: an unknown project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    S = add(db, sess(R, "uploaded", entity_id=MISSING))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == "project 999999999 not found."
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_28__w0_project_refused(db, R, CL):
    """MOBS-PM-28 — PR-1: a W0 project (lower workspace id).
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    PX = proj(db, R, "Zero Job", where="W0")
    S = add(db, sess(R, "uploaded", entity_id=PX.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PX.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_29__w2_project_refused(db, R, CL):
    """MOBS-PM-29 — PR-1: a W2 project (higher workspace id).
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    PX = proj(db, R, "Nine Job", where="W2")
    S = add(db, sess(R, "uploaded", entity_id=PX.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PX.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_30__deleted_machine_refused(db, R, CL):
    """MOBS-PM-30 — PR-1: a deleted machine.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    MD = machine(db, R, "Press 4", deleted=True)
    S = add(db, sess(R, "uploaded", entity_type="machine", entity_id=MD.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("machine", MD.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_31__deleted_work_order_refused(db, R, CL):
    """MOBS-PM-31 — PR-1: a deleted work order.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    WD = wo(db, R, "WO-3", deleted=True)
    S = add(db, sess(R, "uploaded", entity_type="work_order", entity_id=WD.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("work_order", WD.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_32__component_of_deleted_project_refused(db, R, CL):
    """MOBS-PM-32 — PR-1: a component of a deleted project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    PD = proj(db, R, "Old Job", deleted=True)
    CD = comp(db, PD, "Frame")
    S = add(db, sess(R, "uploaded", entity_type="project_component", entity_id=CD.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project_component", CD.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_33__w2_purchase_order_refused(db, R, CL):
    """MOBS-PM-33 — PR-1: a W2 purchase order.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    O9 = po(db, R, "PO-T-009", workspace_id=R.W2.id)
    S = add(db, sess(R, "uploaded", entity_type="purchase_order", entity_id=O9.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("purchase_order", O9.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_34__w0_ticket_refused_even_to_owner(db, R, CL):
    """MOBS-PM-34 — PR-1: a W0 help ticket, even for a W1 owner-role member.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    mg_but(db, R, role="owner")
    T0X = ticket(db, R, "HELP-2026-001", workspace_id=R.W0.id)
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=T0X.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", T0X.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_35__po_id_only_a_machine_has_refused(db, R, CL):
    """MOBS-PM-35 — PR-1: a purchase-order id that only a W1 machine has.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    machine(db, R, "Press 7", id=XID(1))  # no purchase order has id XID(1)
    S = add(db, sess(R, "uploaded", entity_type="purchase_order", entity_id=XID(1)))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("purchase_order", XID(1))
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_36__component_id_only_a_project_has_refused(db, R, CL):
    """MOBS-PM-36 — PR-1: a component id that only a live W1 project has.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    proj(db, R, "Yard", id=XID(2))  # no project component has id XID(2)
    S = add(db, sess(R, "uploaded", entity_type="project_component", entity_id=XID(2)))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project_component", XID(2))
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


def test_mobs_pm_37__live_machine_passes(db, R):
    """MOBS-PM-37 — PR-1 passes: a live machine.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    MA = machine(db, R, "Press 1")
    S = add(db, sess(R, "uploaded", entity_type="machine", entity_id=MA.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    row = reread(db, MobileUploadSession, S.id)
    assert row.status == "consumed"
    assert row.asset_folder == "Dev/" + R.W1.name + "/Machines/Press 1"


def test_mobs_pm_38__scratch_passes(db, R):
    """MOBS-PM-38 — PR-1 passes: scratch.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    S = add(db, sess(R, "uploaded", entity_type="scratch", entity_id=777))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).asset_folder == "Dev/" + R.W1.name + "/Scratch/scratch-777"


@XF2134
def test_mobs_pm_39__plain_member_private_project_refused(db, R, CL):
    """MOBS-PM-39 — PR-2: a plain member, private project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_40__owning_w0_private_refused(db, R, CL):
    """MOBS-PM-40 — PR-2: owning W0 does not open the private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    set_owner(db, R.W0, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_41__owning_w2_private_refused(db, R, CL):
    """MOBS-PM-41 — PR-2: owning W2 does not open the private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    set_owner(db, R.W2, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_42__privileged_only_in_w0_refused(db, R, CL):
    """MOBS-PM-42 — PR-2: privileged only in W0 does not open it.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    member(db, R, R.UG, "owner", ws=R.W0)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_43__privileged_only_in_w2_refused(db, R, CL):
    """MOBS-PM-43 — PR-2: privileged only in W2 does not open it.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    member(db, R, R.UG, "ground-team-manager", ws=R.W2)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_44__other_private_memberships_refused(db, R, CL):
    """MOBS-PM-44 — PR-2: membership of other private projects (lower and higher id).
    Rules: promote_to_attachment R4 [BUG-2134]."""
    PA = proj(db, R, "Alpha", private=True)
    pmem(db, R, PA, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    PB = proj(db, R, "Beta", private=True)
    pmem(db, R, PB, R.UG)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_45__creator_of_other_private_refused(db, R, CL):
    """MOBS-PM-45 — PR-2: having created another private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    proj(db, R, "Alpha", private=True, created_by=R.UG.id)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_46__private_no_creator_refused(db, R, CL):
    """MOBS-PM-46 — PR-2: a private project with no creator, plain member.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    PV = proj(db, R, "Tender 2027", private=True, created_by=None)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_47__suspended_owner_refused(db, R, CL):
    """MOBS-PM-47 — PR-2: a suspended W1 owner membership.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    mg_but(db, R, role="owner", status="suspended")
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_48__component_of_private_refused(db, R, CL):
    """MOBS-PM-48 — PR-2: a component of a private project, plain member.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    PV = proj(db, R, "Tender 2027", private=True)
    CV = comp(db, PV, "Frame")
    S = add(db, sess(R, "uploaded", entity_type="project_component", entity_id=CV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project_component", CV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_49__other_members_ticket_refused(db, R, CL):
    """MOBS-PM-49 — PR-2: another member's ticket, plain role.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_50__creator_of_other_tickets_refused(db, R, CL):
    """MOBS-PM-50 — PR-2: creating other tickets (lower and higher id).
    Rules: promote_to_attachment R4 [BUG-2134]."""
    ticket(db, R, "HELP-2026-001", created_by=R.UG.id)
    TK = ticket(db, R, "HELP-2026-002")
    ticket(db, R, "HELP-2026-003", created_by=R.UG.id)
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_51__ticket_no_creator_refused(db, R, CL):
    """MOBS-PM-51 — PR-2: a ticket with no creator, plain role.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    TK = ticket(db, R, "HELP-2026-001", created_by=None)
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_52__capital_owner_role_refused(db, R, CL):
    """MOBS-PM-52 — PR-2: a W1 membership role "Owner" with a capital does not open a ticket.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    mg_but(db, R, role="Owner")
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert cl_called(CL) == []
    # Then 5
    assert unchanged(db, S, before_s)


def test_mobs_pm_53__w1_owner_private_project(db, R):
    """MOBS-PM-53 — PR-2 grant: the W1 owner, private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    set_owner(db, R.W1, R.UG)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_54__active_owner_role_private_project(db, R):
    """MOBS-PM-54 — PR-2 grant: an active owner-role member, private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    mg_but(db, R, role="owner")
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_55__creator_private_project(db, R):
    """MOBS-PM-55 — PR-2 grant: the creator, private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    PV = proj(db, R, "Tender 2027", private=True, created_by=R.UG.id)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_56__project_member_private_project(db, R):
    """MOBS-PM-56 — PR-2 grant: a project member, private project.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    PV = proj(db, R, "Tender 2027", private=True)
    pmem(db, R, PV, R.UG)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_57__privileged_member_creatorless_private(db, R):
    """MOBS-PM-57 — PR-2 grant: a privileged member, private project with no creator.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    mg_but(db, R, role="ground-team-manager")
    PV = proj(db, R, "Tender 2027", private=True, created_by=None)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_58__ticket_creator(db, R):
    """MOBS-PM-58 — PR-2 grant: the ticket's creator.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    TK = ticket(db, R, "HELP-2026-001", created_by=R.UG.id)
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_59__active_owner_role_others_ticket(db, R):
    """MOBS-PM-59 — PR-2 grant: an active owner-role member opens another member's ticket.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    mg_but(db, R, role="owner")
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


def test_mobs_pm_60__platform_admin_creatorless_ticket(db, R):
    """MOBS-PM-60 — PR-2 grant: a platform admin opens a ticket with no creator.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    R.UG.is_platform_admin = True
    db.flush()
    TK = ticket(db, R, "HELP-2026-001", created_by=None)
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


@XF2134
def test_mobs_pm_61__removed_owner_private_refused(db, R, CL):
    """MOBS-PM-61 — PR-2: a removed (inactive) W1 owner membership does not open a private project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    mg_but(db, R, role="owner", **REMOVED)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_62__suspended_gtm_ticket_refused(db, R, CL):
    """MOBS-PM-62 — PR-2: a suspended W1 ground-team-manager membership does not open another member's ticket.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    mg_but(db, R, role="ground-team-manager", status="suspended")
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_63__removed_owner_ticket_refused(db, R, CL):
    """MOBS-PM-63 — PR-2: a removed (inactive) W1 owner membership does not open another member's ticket.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    mg_but(db, R, role="owner", **REMOVED)
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_64__older_privileged_rows_elsewhere_refused(db, R, CL):
    """MOBS-PM-64 — PR-2: privileged rows in W0 and W2 older than the W1 row do not open a private project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    drop_mg(db, R)
    member(db, R, R.UG, "owner", ws=R.W0)
    member(db, R, R.UG, "ground-team-manager", ws=R.W2)
    member(db, R, R.UG, "ground-team")  # the W1 row, now the newest
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_65__owner_only_in_w0_ticket_refused(db, R, CL):
    """MOBS-PM-65 — PR-2: an owner role only in W0 does not open another member's W1 ticket.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    member(db, R, R.UG, "owner", ws=R.W0)
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("support_ticket", TK.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


def test_mobs_pm_66__non_member_workspace_machine(db, R):
    """MOBS-PM-66 — PR-2 passes: a caller with no W1 membership attaches to a workspace-wide machine.
    Rules: promote_to_attachment R4 [BUG-2134]."""
    drop_mg(db, R)
    MA = machine(db, R, "Press 1")
    S = add(db, sess(R, "uploaded", entity_type="machine", entity_id=MA.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


@XF2134
def test_mobs_pm_67__no_membership_private_refused(db, R, CL):
    """MOBS-PM-67 — PR-2: no W1 membership at all: a private project stays closed.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    drop_mg(db, R)
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


def test_mobs_pm_68__stored_delivery_type_used_for_move(db, R, CL):
    """MOBS-PM-68 — a stored non-default delivery type is used for the move.
    Rules: promote_to_attachment R7."""
    S = add(db, sess(R, "uploaded", delivery_type="upload"))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.public_id == DEST(R)
    # Then 2
    CL.rr.assert_called_once()
    assert kw(CL.rr)["from_public_id"] == STG
    assert kw(CL.rr)["to_public_id"] == DEST(R)
    assert kw(CL.rr)["delivery_type"] == "upload"
    assert kw(CL.rr)["resource_type"] == "image"


@XF2134
def test_mobs_pm_69__platform_admin_no_membership_private_refused(db, R, CL):
    """MOBS-PM-69 — PR-2: a platform admin with no W1 membership is refused a private project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    drop_mg(db, R)
    R.UG.is_platform_admin = True
    db.flush()
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


@XF2134
def test_mobs_pm_70__platform_admin_no_membership_private_component_refused(db, R, CL):
    """MOBS-PM-70 — PR-2: a platform admin with no W1 membership is refused a component of a private project.
    Rules: promote_to_attachment R4, R5 [BUG-2134]."""
    drop_mg(db, R)
    R.UG.is_platform_admin = True
    db.flush()
    PV = proj(db, R, "Tender 2027", private=True)
    CV = comp(db, PV, "Frame")
    S = add(db, sess(R, "uploaded", entity_type="project_component", entity_id=CV.id))
    before = counts(db)
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project_component", CV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
    # Then 7
    assert counts(db) == before


def test_mobs_pm_71__workspace_owner_plain_role_attaches_to_others_ticket(db, R):
    """MOBS-PM-71 — PR-2 grant: the workspace owner with a plain role attaches to another member's ticket.
    Rules: promote_to_attachment R4 [BUG-2134, BUG-2103]."""
    set_owner(db, R.W1, R.UG)
    TK = ticket(db, R, "HELP-2026-001")
    S = add(db, sess(R, "uploaded", entity_type="support_ticket", entity_id=TK.id))
    result = M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    assert reread(db, MobileUploadSession, S.id).status == "consumed"


@XF2134
def test_mobs_pm_72__hidden_private_project_oversized_not_found(db, R, CL):
    """MOBS-PM-72 — PR-2 before the size check: a hidden private project with an oversized file answers 404.
    Rules: promote_to_attachment R4 [BUG-2134] (G6)."""
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id, file_size=10485761))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_73__hidden_private_project_bad_type_not_found(db, R, CL):
    """MOBS-PM-73 — PR-2 before the type check: a hidden private project with a mismatched MIME type answers 404.
    Rules: promote_to_attachment R4 [BUG-2134] (G6)."""
    PV = proj(db, R, "Tender 2027", private=True)
    S = add(db, sess(R, "uploaded", entity_id=PV.id, mime_type="image/png"))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)


@XF2134
def test_mobs_pm_74__hidden_private_project_at_capacity_not_found(db, R, CL):
    """MOBS-PM-74 — PR-2 before the limit check: a hidden private project at its capacity answers 404.
    Rules: promote_to_attachment R4 [BUG-2134] (G6)."""
    PV = proj(db, R, "Tender 2027", private=True)
    full(db, R, PV)
    S = add(db, sess(R, "uploaded", entity_id=PV.id))
    before_s = snap(db, S)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.promote_to_attachment(db, session=S, workspace=R.W1, user=R.UG, file_name=None, note=None)
    # Then 2
    assert str(exc.value) == NF("project", PV.id)
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert cl_called(CL) == []
    # Then 6
    assert unchanged(db, S, before_s)
