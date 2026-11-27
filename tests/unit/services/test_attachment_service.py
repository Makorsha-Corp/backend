"""Unit tests for app/services/attachment_service.py.

Implements tests/unit/services/attachment_service.cases.md (revision 4), one test
per card, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Every test commits its Given rows (commit point).

Patched, as Conventions name them: Cloudinary on `app.managers.attachment_manager`
only (`generate_upload_signature`, `get_resource`, `destroy_resource`,
`build_signed_delivery_url`, each with autospec), `uuid.uuid4` and `time.time`
there, and the `settings` attributes; the commit / rollback spies, failing commit,
failing refresh (also after commit) and order log wrap the session's own methods. Nothing reaches the
network.

Each test carries a `# [claude] <ID>` comment; `# Then N` marks the checks of the
card's Then line N. Card names map to `S.<name>` (standing rows) or locals.
"""

# ruff: noqa: SIM117  (Conventions prescribe the nested `with` around the When)
import inspect
import logging
import os
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

import app.core.config as config_mod
import app.managers.attachment_manager as mgr_mod
import app.services.attachment_service as svc_mod
from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.managers.attachment_manager import AttachmentLimitError
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.attachment_link import AttachmentLink
from app.models.enums import AttachmentEntityTypeEnum
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_member import ProjectMember
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.attachment import AttachmentSignRequest
from app.services.attachment_service import (
    AttachmentConfirmError,
    AttachmentNotFoundError,
    AttachmentValidationError,
    attachment_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

svc = attachment_service
MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
TOKEN = "0123456789abcdef0123456789abcdef"
BSU = "https://signed.example/a"
RES = {
    "resource_type": "image",
    "format": "jpg",
    "bytes": 1234,
    "version": 1700000000,
    "secure_url": "https://res.example/s.jpg",
    "url": "http://res.example/u.jpg",
    "width": 800,
    "height": 600,
    "asset_id": "a" * 32,
    "etag": "e" * 32,
}


def XID(k):
    """XID(k): an id no sequence hands out."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def NFA(i):
    return "Attachment " + str(i) + " not found."


def NF(t, i):
    return t + " " + str(i) + " not found."


def ET(t):
    return AttachmentEntityTypeEnum(t)


def PID1(S):
    return "development/ws-" + str(S.W1.id) + "/" + TOKEN


X1434 = pytest.mark.xfail(
    strict=True,
    reason="BUG-1434: A failed upload keeps using up one of the record's 25 attachment places",
)
X1870 = pytest.mark.xfail(
    strict=True,
    reason="BUG-1870: Any member lists and adds attachments of a private project",
)
X1950 = pytest.mark.xfail(
    strict=True,
    reason="BUG-1950: Any member lists and adds attachments on another member's help ticket",
)
X2090 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2090: An upload can be signed for a record that does not exist, is deleted, "
    "or belongs to another workspace",
)
X2091 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2091: Reading, confirming and deleting an attachment by id ignores who may open its record",
)
X2095 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2095: A failed confirm is recorded, then the record is rolled back",
)
X2096 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2096: 'Cloudinary not configured' at confirm marks the user's upload failed and answers 400",
)
X2097 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2097: Deleting an attachment already deleted deletes it again",
)
X2099 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2099: Deleting a pending or failed upload leaves its file in Cloudinary",
)
X2100 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2100: A failed Cloudinary delete of an attachment's file leaves no trace",
)
X2200 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2200: The attachment list of an unknown or deleted record answers with its files",
)
X2201 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2201: The attachment list reads each attachment's links with its own query",
)
X2202 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2202: Deleting an attachment deletes its Cloudinary file before the delete is saved",
)


# --------------------------------------------------------------------------- #
# Conventions -> Settings and Cloudinary (every test)
# --------------------------------------------------------------------------- #

_SETTINGS_OBJS = (config_mod.settings, mgr_mod.settings, svc_mod.settings)
_SETTINGS = {
    "CLOUDINARY_UPLOAD_ENV": "development",
    "ENVIRONMENT": "development",
    "CLOUDINARY_CLOUD_NAME": "demo-cloud",
    "CLOUDINARY_API_KEY": "123456",
    "CLOUDINARY_API_SECRET": "s3cret",
    "MAX_ATTACHMENTS_PER_ENTITY": 25,
}


@pytest.fixture(autouse=True)
def cl_settings(monkeypatch):
    for obj in _SETTINGS_OBJS:
        for name, value in _SETTINGS.items():
            monkeypatch.setattr(obj, name, value)


def setting(monkeypatch, name, value):
    """Given line "settings: NAME value"."""
    for obj in _SETTINGS_OBJS:
        monkeypatch.setattr(obj, name, value)


@pytest.fixture(autouse=True)
def cl():
    """gus / gr / dr / bsu (autospec) plus fixed uuid and fixed time."""
    targets = {
        "gus": "generate_upload_signature",
        "gr": "get_resource",
        "dr": "destroy_resource",
        "bsu": "build_signed_delivery_url",
    }
    ns = SimpleNamespace()
    with ExitStack() as stack:
        for key, name in targets.items():
            setattr(
                ns,
                key,
                stack.enter_context(
                    patch(f"app.managers.attachment_manager.{name}", autospec=True)
                ),
            )
        ns.gus.return_value = "sig-x"
        ns.gr.return_value = dict(RES)
        ns.dr.return_value = {"result": "ok"}
        ns.bsu.return_value = BSU
        stack.enter_context(
            patch(
                "app.managers.attachment_manager.uuid.uuid4",
                return_value=uuid.UUID(TOKEN),
            )
        )
        stack.enter_context(
            patch(
                "app.managers.attachment_manager.time.time", return_value=1767225600.9
            )
        )
        yield ns


def kw(m):
    ba = inspect.signature(m).bind(*m.call_args.args, **m.call_args.kwargs)
    ba.apply_defaults()
    return dict(ba.arguments)


def cl_untouched(cl):
    return (cl.gus.called, cl.gr.called, cl.dr.called, cl.bsu.called)


UNTOUCHED = (False, False, False, False)


# --------------------------------------------------------------------------- #
# Conventions -> Caller (PR-5)
# --------------------------------------------------------------------------- #


def call_uid(db, fn, U, **kw_):
    """Adds user_id= only when fn already has that parameter."""
    if "user_id" in inspect.signature(fn).parameters:
        return fn(db, **kw_, user_id=U.id)
    return fn(db, **kw_)


def la(db, U, **kw_):
    return call_uid(db, svc.list_attachments, U, **kw_)


def ga(db, U, **kw_):
    return call_uid(db, svc.get_attachment, U, **kw_)


def pg(db, U, **kw_):
    return call_uid(db, svc.get_pdf_page_image, U, **kw_)


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows and Given rows
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def member(db, U, role, ws, status="active"):
    return _add(
        db,
        WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status),
    )


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db, name="Ana Rahman")
    s.U2 = make_profile(db, name="Bilal Khan")
    s.UG = make_profile(db, name="Mia Khan")
    member(db, s.U1, "ground-team", s.W1)
    member(db, s.U2, "owner", s.W1)
    s.MG = member(db, s.UG, "ground-team", s.W1)
    s.F0 = _add(
        db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0")
    )
    s.F1 = _add(
        db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1")
    )
    s.F9 = _add(
        db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9")
    )
    return s


def _where(S, where):
    return {"W0": (S.W0, S.F0), "W1": (S.W1, S.F1), "W2": (S.W2, S.F9)}[where]


def mach(db, S, name, where="W1", deleted=False, **over):
    ws, f = _where(S, where)
    fields = {"workspace_id": ws.id, "factory_id": f.id, "name": name}
    if deleted:
        fields.update(
            is_deleted=True, is_active=False, deleted_at=T0, deleted_by=S.U1.id
        )
    fields.update(over)
    return _add(db, Machine(**fields))


def item(db, S, name, sku, **over):
    fields = {
        "workspace_id": S.W1.id,
        "name": name,
        "name_normalized": name.lower(),
        "unit": "pcs",
        "sku": sku,
    }
    fields.update(over)
    return _add(db, Item(**fields))


def proj(db, S, name, private=False, deleted=False, **over):
    fields = {
        "workspace_id": S.W1.id,
        "factory_id": S.F1.id,
        "name": name,
        "description": "Main",
        "created_by": S.U1.id,
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Project(**fields))


def pmem(db, S, P, U):
    return _add(
        db,
        ProjectMember(
            workspace_id=P.workspace_id,
            project_id=P.id,
            user_id=U.id,
            assigned_by=S.U1.id,
        ),
    )


def comp(db, P, name):
    return _add(
        db, ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name=name)
    )


def ticket(db, S, number, **over):
    fields = {
        "workspace_id": S.W1.id,
        "ticket_number": number,
        "title": "Printer jam",
        "description": "It jams",
        "created_by": S.U1.id,
    }
    fields.update(over)
    return _add(db, HelpTicket(**fields))


def wo(db, S, number, deleted=False):
    """wo("N"): WorkOrderType "Repair" first, then the work order; `deleted` as Conventions."""
    wt = _add(db, WorkOrderType(workspace_id=S.W1.id, name="Repair"))
    fields = {
        "workspace_id": S.W1.id,
        "work_order_number": number,
        "title": "Fix press",
        "factory_id": S.F1.id,
        "work_order_type_id": wt.id,
    }
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    return _add(db, WorkOrder(**fields))


def att(
    db, S, pid, ready=False, failed=False, pdf=False, gone=False, where="W1", **over
):
    """att("pid"); ready / failed / pdf / gone / W0 att / W2 att as Conventions."""
    ws, _ = _where(S, where)
    fields = {
        "workspace_id": ws.id,
        "file_name": "photo.jpg",
        "mime_type": "image/jpeg",
        "file_size": 1000,
        "uploaded_by": S.U1.id,
        "upload_status": "pending",
        "public_id": pid,
        "resource_type": "image",
        "delivery_type": "authenticated",
        "note": "Front",
    }
    if ready:
        fields.update(upload_status="ready", format="jpg", version=1700000000)
    if failed:
        fields.update(upload_status="failed")
    if pdf:
        fields.update(file_name="plan.pdf", mime_type="application/pdf", format="pdf")
    if gone:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Attachment(**fields))


def link(db, S, A, etype, P):
    """link(A, "type", P); P may be a number."""
    return _add(
        db,
        AttachmentLink(
            workspace_id=A.workspace_id,
            attachment_id=A.id,
            entity_type=etype,
            entity_id=P if isinstance(P, int) else P.id,
            linked_by=S.U1.id,
        ),
    )


_KIND = {
    Machine: "machine",
    Project: "project",
    ProjectComponent: "project_component",
    Item: "item",
    HelpTicket: "support_ticket",
}


def fill(db, S, P, n, status):
    """fill(P, n, "status"): returns the attachments it built."""
    out = []
    for i in range(1, n + 1):
        extra = {"format": "jpg", "version": 1700000000} if status == "ready" else {}
        a = att(db, S, f"fill-{i}", upload_status=status, **extra)
        link(db, S, a, _KIND[type(P)], P)
        out.append(a)
    return out


def REQ(etype, eid):
    return AttachmentSignRequest(
        entity_type=etype,
        entity_id=eid,
        file_name="plan.pdf",
        mime_type="application/pdf",
        file_size=1000,
        note="Site plan",
    )


# --------------------------------------------------------------------------- #
# Conventions -> commit point, pending changes, named checks
# --------------------------------------------------------------------------- #


def commit_point(db):
    db.commit()


def pending_x(db, S):
    """pending X; returns X_ID."""
    x = Factory(workspace_id=S.W2.id, name="Factory X", abbreviation="FX")
    db.add(x)
    db.flush()
    return x.id


def x_count(db, x_id):
    return db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": x_id})


def pending_edit(S):
    S.F9.name = "Factory Edited"


def reread(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


def snap(db, model, rid):
    """unchanged(X): every column, read fresh."""
    row = reread(db, model, rid)
    return {c.key: getattr(row, c.key) for c in sa_inspect(model).mapper.column_attrs}


_TABLES = (
    "attachments",
    "attachment_links",
    "attachment_ledger",
    "machine_activity_events",
    "project_events",
)


def counts(db):
    """nothing written: row counts of the five tables (all workspaces)."""
    return {t: db.scalar(text(f"SELECT count(*) FROM {t}")) for t in _TABLES}


def ledger_of(db, aid):
    db.expire_all()
    return (
        db.query(AttachmentLedger)
        .filter(AttachmentLedger.attachment_id == aid)
        .order_by(AttachmentLedger.id)
        .all()
    )


def links_of(db, aid):
    db.expire_all()
    return (
        db.query(AttachmentLink)
        .filter(AttachmentLink.attachment_id == aid)
        .order_by(AttachmentLink.id)
        .all()
    )


def events_of(db, M):
    return [
        tuple(r)
        for r in db.execute(
            text(
                "SELECT event_type, description, performed_by FROM machine_activity_events "
                "WHERE machine_id = :i ORDER BY id"
            ),
            {"i": M.id},
        ).all()
    ]


def att_rows(db, **where):
    db.expire_all()
    return db.query(Attachment).filter_by(**where).all()


def ids(r):
    return {i.id for i in r.items}


# Convention "warnings": caplog at WARNING (root logger) before the When
def warnings_on(caplog):
    caplog.set_level(logging.WARNING)


# Convention "warned(p)"
def warned(caplog, p):
    return any(
        r.levelno == logging.WARNING and p in r.getMessage() for r in caplog.records
    )


def lk(x):
    return [(lnk.entity_type.value, lnk.entity_id) for lnk in x.links]


@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Convention "failing refresh after commit": refreshes before the commit (the
# manager's own) run normally; a refresh after the commit spy was called raises
@contextmanager
def failing_refresh_after_commit(db):
    real_r = db.refresh
    with patch.object(db, "commit", wraps=db.commit) as cm:

        def late(*a, **k):
            if cm.called:
                raise RuntimeError("boom")
            return real_r(*a, **k)

        with patch.object(db, "refresh", side_effect=late) as rf:
            yield cm, rf


@contextmanager
def order_log(db, cl):
    order = []

    def _dr(*a, **k):
        order.append("dr")
        return {"result": "ok"}

    cl.dr.side_effect = _dr
    real = db.commit
    with patch.object(
        db, "commit", side_effect=lambda: (order.append("commit"), real())[1]
    ):
        yield order


@contextmanager
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, parameters, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", rec)


def link_stmts(stmts):
    return sum(1 for s in stmts if "attachment_links" in s)


# --------------------------------------------------------------------------- #
# AttachmentService.sign_upload
# --------------------------------------------------------------------------- #


# [claude] ATSV-S-01
def test_atsv_s_01__sign_answers_the_upload_parameters_and_commits_a_pending_attachment(
    db, S, cl
):
    """ATSV-S-01 — sign answers the upload parameters and commits a pending attachment.
    Rules: sign_upload R3, TC1"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    result = svc.sign_upload(
        db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id)
    )

    # Then 1
    assert type(result).__name__ == "AttachmentSignResponse"
    # Then 2
    assert result.public_id == PID1(S)
    # Then 3
    assert result.asset_folder == "Dev/" + S.W1.name + "/Machines/Lathe"
    assert result.display_name == "plan.pdf"
    # Then 4
    assert result.timestamp == 1767225600
    assert result.signature == "sig-x"
    assert result.type == "authenticated"
    # Then 5
    assert result.resource_type == "image"
    assert (
        result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"
    )
    # Then 6
    assert result.cloud_name == "demo-cloud"
    assert result.api_key == "123456"
    # Then 7
    assert cl.gus.call_count == 1
    assert kw(cl.gus)["public_id"] == PID1(S)
    # Then 8
    assert cl.gr.called is False
    assert cl.dr.called is False
    # Then 9
    db.rollback()
    row = reread(db, Attachment, result.attachment_id)
    assert row.upload_status == "pending"
    assert row.public_id == PID1(S)
    assert row.workspace_id == S.W1.id
    assert row.uploaded_by == S.UG.id
    assert row.file_name == "plan.pdf"
    assert row.note == "Site plan"


# [claude] ATSV-S-02
def test_atsv_s_02__the_link_and_the_pending_ledger_row_are_committed_with_the_caller(
    db, S
):
    """ATSV-S-02 — the link and the pending ledger row are committed with the caller.
    Rules: sign_upload R3, TC1"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    result = svc.sign_upload(
        db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id)
    )

    # Then 1
    assert result.attachment_id is not None
    # Then 2
    db.rollback()
    links = links_of(db, result.attachment_id)
    assert len(links) == 1
    assert links[0].workspace_id == S.W1.id
    assert links[0].entity_type == "machine"
    assert links[0].entity_id == M1.id
    assert links[0].linked_by == S.UG.id
    # Then 3
    ledger = ledger_of(db, result.attachment_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "pending"
    assert ledger[0].performed_by == S.UG.id
    assert ledger[0].entity_type == "machine"
    assert ledger[0].entity_id == M1.id
    # Then 4
    assert events_of(db, M1) == []


# [claude] ATSV-S-03
def test_atsv_s_03__an_invalid_file_is_refused_first_nothing_written(db, S, cl):
    """ATSV-S-03 — an invalid file is refused first; nothing written.
    Rules: sign_upload R1"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.sign_upload(
            db,
            workspace=S.W1,
            user=S.UG,
            payload=AttachmentSignRequest(
                entity_type="machine",
                entity_id=M1.id,
                file_name="plan.pdf",
                mime_type="application/pdf",
                file_size=10485761,
            ),
        )
    # Then 2
    assert (
        str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."
    )
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_untouched(cl) == UNTOUCHED


# [claude] ATSV-S-04
def test_atsv_s_04__a_full_record_is_refused_nothing_written(db, S):
    """ATSV-S-04 — a full record is refused; nothing written.
    Rules: sign_upload R2"""
    M1 = mach(db, S, "Lathe")
    fill(db, S, M1, 25, "ready")
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id))
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-S-05
def test_atsv_s_05__cloudinary_not_configured_after_the_flush_everything_rolled_back(
    db, S, monkeypatch
):
    """ATSV-S-05 — Cloudinary not configured after the flush: everything rolled back.
    Rules: sign_upload R4, TC3"""
    setting(monkeypatch, "CLOUDINARY_API_KEY", "")
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        with spies(db) as (_cm, rb):
            svc.sign_upload(
                db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id)
            )
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert (
        db.scalar(
            text("SELECT count(*) FROM attachments WHERE public_id = :p"),
            {"p": PID1(S)},
        )
        == 0
    )


# [claude] ATSV-S-06
def test_atsv_s_06__any_other_error_reaches_the_caller_as_the_same_object_and_discards_pending(
    db, S, cl
):
    """ATSV-S-06 — any other error reaches the caller as the same object and discards other pending changes.
    Rules: sign_upload R6, TC3"""
    M1 = mach(db, S, "Lathe")
    E = RuntimeError("sig down")
    cl.gus.side_effect = E
    commit_point(db)
    before = counts(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id))
    # Then 2
    assert exc.value is E
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert db.execute(text("SELECT 1")).scalar() == 1


# [claude] ATSV-S-07
def test_atsv_s_07__a_failing_commit_rolls_back_nothing_saved(db, S):
    """ATSV-S-07 — a failing commit rolls back; nothing saved.
    Rules: sign_upload R5, TC4"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.sign_upload(
                db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id)
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] ATSV-S-08
def test_atsv_s_08__a_failing_reread_after_the_commit_leaves_the_attachment_saved(
    db, S
):
    """ATSV-S-08 — a failing re-read after the commit leaves the attachment saved.
    Rules: sign_upload R5, TC5"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    m1_id, ug_id, pid1 = M1.id, S.UG.id, PID1(S)
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.sign_upload(
                db, workspace=S.W1, user=S.UG, payload=REQ("machine", m1_id)
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    rows = att_rows(db, public_id=pid1)
    assert len(rows) == 1
    assert rows[0].upload_status == "pending"
    assert rows[0].uploaded_by == ug_id
    # Then 3
    db.expire_all()
    lrows = (
        db.query(AttachmentLink).filter_by(entity_type="machine", entity_id=m1_id).all()
    )
    assert len(lrows) == 1


# [claude] ATSV-S-09
@X2090
def test_atsv_s_09__a_deleted_machine_is_refused_as_not_found_nothing_written(
    db, S, cl
):
    """ATSV-S-09 — a deleted machine is refused as not found; nothing written.
    Rules: sign_upload R2 [BUG-2090]"""
    M1 = mach(db, S, "Lathe", deleted=True)
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("machine", M1.id))
    # Then 2
    assert str(exc.value) == NF("machine", M1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before
    # Then 5
    assert cl_untouched(cl) == UNTOUCHED


# [claude] ATSV-S-10
@X2090
def test_atsv_s_10__a_w0_machine_is_refused_as_not_found_nothing_written(db, S):
    """ATSV-S-10 — a W0 machine is refused as not found; nothing written.
    Rules: sign_upload R2 [BUG-2090]; HR-16"""
    M0 = mach(db, S, "Lathe", where="W0")
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("machine", M0.id))
    # Then 2
    assert str(exc.value) == NF("machine", M0.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-S-11
@X1870
def test_atsv_s_11__a_private_project_the_caller_may_not_open_is_refused(db, S):
    """ATSV-S-11 — a private project the caller may not open is refused.
    Rules: sign_upload R2 [BUG-1870]; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("project", P1.id))
    # Then 2
    assert str(exc.value) == NF("project", P1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-S-12
@X1870
def test_atsv_s_12__membership_of_another_private_project_does_not_open_this_one(db, S):
    """ATSV-S-12 — membership of another private project does not open this one.
    Rules: sign_upload R2 [BUG-1870]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.sign_upload(db, workspace=S.W1, user=S.UG, payload=REQ("project", P1.id))
    # Then 2
    assert str(exc.value) == NF("project", P1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-S-13
@X1950
def test_atsv_s_13__an_owner_role_held_only_in_w2_does_not_open_another_members_w1_ticket(
    db, S
):
    """ATSV-S-13 — an owner role held only in W2 does not open another member's W1 ticket.
    Rules: sign_upload R2 [BUG-1950]; PR-2, PR-5 (grant held in a different workspace)"""
    member(db, S.UG, "owner", S.W2)
    T1 = ticket(db, S, "HT-1")
    commit_point(db)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.sign_upload(
            db, workspace=S.W1, user=S.UG, payload=REQ("support_ticket", T1.id)
        )
    # Then 2
    assert str(exc.value) == NF("support_ticket", T1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-S-14
def test_atsv_s_14__a_member_of_the_private_project_signs_the_caller_is_the_uploader(
    db, S
):
    """ATSV-S-14 — a member of the private project signs; the caller is the uploader.
    Rules: sign_upload R2, R3; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    commit_point(db)
    result = svc.sign_upload(
        db, workspace=S.W1, user=S.UG, payload=REQ("project", P1.id)
    )

    # Then 1
    assert result.public_id == PID1(S)
    assert result.asset_folder == "Dev/" + S.W1.name + "/Projects/Tender"
    # Then 2
    db.rollback()
    row = reread(db, Attachment, result.attachment_id)
    assert row.uploaded_by == S.UG.id
    assert row.upload_status == "pending"
    # Then 3
    links = links_of(db, result.attachment_id)
    assert len(links) == 1
    assert links[0].entity_type == "project"
    assert links[0].entity_id == P1.id


# --------------------------------------------------------------------------- #
# AttachmentService.confirm_upload
# --------------------------------------------------------------------------- #


# [claude] ATSV-CF-01
def test_atsv_cf_01__confirm_marks_ready_commits_and_answers_the_reread_row(db, S, cl):
    """ATSV-CF-01 — confirm marks ready, commits, and answers the re-read row.
    Rules: confirm_upload R1, TC1, TC2"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = svc.confirm_upload(
        db, workspace_id=S.W1.id, attachment_id=A1.id, performed_by=S.UG.id
    )

    # Then 1
    assert type(result).__name__ == "AttachmentResponse"
    assert result.id == A1.id
    # Then 2
    assert result.upload_status == "ready"
    assert result.format == "jpg"
    assert result.version == 1700000000
    # Then 3
    assert result.file_url == "https://res.example/s.jpg"
    assert result.urls.preview_url == BSU
    # Then 4
    assert result.uploaded_at is not None
    assert lk(result) == [("machine", M1.id)]
    # Then 5
    assert cl.gr.call_count == 1
    assert kw(cl.gr)["public_id"] == "pid-1"
    # Then 6
    db.rollback()
    row = reread(db, Attachment, A1.id)
    assert row.upload_status == "ready"
    assert row.file_url == "https://res.example/s.jpg"
    assert row.width == 800
    assert row.height == 600


# [claude] ATSV-CF-02
def test_atsv_cf_02__the_ready_ledger_row_and_the_activity_entry_carry_the_caller(
    db, S
):
    """ATSV-CF-02 — the ready ledger row and the activity entry carry the caller.
    Rules: confirm_upload R1, TC1; PR-5 (caller passed down)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = svc.confirm_upload(
        db, workspace_id=S.W1.id, attachment_id=A1.id, performed_by=S.UG.id
    )

    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    db.rollback()
    ledger = ledger_of(db, A1.id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "ready"
    assert ledger[0].performed_by == S.UG.id
    assert ledger[0].entity_type == "machine"
    assert ledger[0].entity_id == M1.id
    # Then 3
    assert events_of(db, M1) == [("attachment_added", "Attached photo.jpg", S.UG.id)]


# [claude] ATSV-CF-03
def test_atsv_cf_03__performed_by_none_the_uploader_is_the_actor(db, S):
    """ATSV-CF-03 — performed_by None: the uploader is the actor.
    Rules: confirm_upload Inputs (performed_by None -> uploader), R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = svc.confirm_upload(db, workspace_id=S.W1.id, attachment_id=A1.id)

    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    db.rollback()
    ledger = ledger_of(db, A1.id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "ready"
    assert ledger[0].performed_by == S.U1.id


# [claude] ATSV-CF-04
def test_atsv_cf_04__an_already_ready_attachment_is_answered_unchanged_nothing_written(
    db, S, cl
):
    """ATSV-CF-04 — an already ready attachment is answered unchanged; nothing written.
    Rules: confirm_upload R2"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)
    result = svc.confirm_upload(
        db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    assert result.upload_status == "ready"
    # Then 2
    assert cl.gr.called is False
    # Then 3
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 4
    assert counts(db) == before


# [claude] ATSV-CF-05
def test_atsv_cf_05__a_failed_cloudinary_lookup_reaches_the_caller_as_the_confirm_error(
    db, S, cl
):
    """ATSV-CF-05 — a failed Cloudinary lookup reaches the caller as the confirm error.
    Rules: confirm_upload R3 (part that holds today)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.side_effect = RuntimeError("boom")
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=A1.id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert cl.gr.call_count == 1
    # Then 5
    assert events_of(db, M1) == []


# [claude] ATSV-CF-06
@X2095
def test_atsv_cf_06__the_failure_record_of_a_failed_lookup_is_committed_then_the_error_returned(
    db, S, cl
):
    """ATSV-CF-06 — the failure record of a failed lookup is committed, then the error returned.
    Rules: confirm_upload R3 [BUG-2095]; HR-13"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.side_effect = RuntimeError("boom")
    commit_point(db)
    a1_id = A1.id

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: boom"
    # Then 3
    db.rollback()
    assert reread(db, Attachment, a1_id).upload_status == "failed"
    # Then 4
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "failed"
    assert ledger[0].notes == "boom"
    assert ledger[0].performed_by == S.UG.id


# [claude] ATSV-CF-07
def test_atsv_cf_07__a_file_cloudinary_describes_wrongly_reaches_the_caller_as_the_confirm_error(
    db, S, cl
):
    """ATSV-CF-07 — a file Cloudinary describes wrongly reaches the caller as the confirm error.
    Rules: confirm_upload R3 (part that holds today)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.return_value = {**RES, "resource_type": "raw", "format": "exe"}
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentConfirmError):
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=A1.id, performed_by=S.UG.id
        )
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert cl.gr.call_count == 1


# [claude] ATSV-CF-08
@X2095
def test_atsv_cf_08__the_failure_record_of_a_refused_file_is_committed_then_the_error_returned(
    db, S, cl
):
    """ATSV-CF-08 — the failure record of a refused file is committed, then the error returned.
    Rules: confirm_upload R3 [BUG-2095]; HR-13"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.return_value = {**RES, "resource_type": "raw", "format": "exe"}
    commit_point(db)
    a1_id = A1.id

    # Then 1
    with pytest.raises(AttachmentConfirmError):
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    db.rollback()
    assert reread(db, Attachment, a1_id).upload_status == "failed"
    # Then 3
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "failed"
    assert ledger[0].performed_by == S.UG.id


# [claude] ATSV-CF-09
@X2095
def test_atsv_cf_09__when_the_commit_of_the_failure_record_fails_the_commits_error_reaches_the_caller(
    db, S, cl
):
    """ATSV-CF-09 — when the commit of the failure record fails, the commit's error reaches the caller.
    Rules: confirm_upload R3 [BUG-2095], TC4"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.side_effect = RuntimeError("lookup")
    commit_point(db)
    a1_id = A1.id
    before = counts(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.confirm_upload(
                db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, Attachment, a1_id).upload_status == "pending"
    # Then 4
    assert counts(db) == before


# [claude] ATSV-CF-10
def test_atsv_cf_10__no_public_id_the_refusal_wrote_nothing_nothing_committed(
    db, S, cl
):
    """ATSV-CF-10 — no public_id: the refusal wrote nothing, nothing committed.
    Rules: confirm_upload R3 (refusal that wrote nothing)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", public_id=None)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == "Attachment has no public_id."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl.gr.called is False


# [claude] ATSV-CF-11
def test_atsv_cf_11__an_unknown_id_rolls_back_and_discards_other_pending_changes(
    db, S, cl
):
    """ATSV-CF-11 — an unknown id rolls back and discards other pending changes.
    Rules: confirm_upload R4, TC3, Errors row 1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    before = counts(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        with spies(db) as (_cm, rb):
            svc.confirm_upload(
                db, workspace_id=S.W1.id, attachment_id=MISSING, performed_by=S.UG.id
            )
    # Then 2
    assert str(exc.value) == NFA(MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before
    # Then 7
    assert cl_untouched(cl) == UNTOUCHED


# [claude] ATSV-CF-12
def test_atsv_cf_12__a_w0_attachment_is_not_found(db, S):
    """ATSV-CF-12 — a W0 attachment is not found.
    Rules: confirm_upload R4; HR-16"""
    A0 = att(db, S, "pid-0", where="W0")
    link(db, S, A0, "scratch", 1)
    commit_point(db)
    a0_id = A0.id
    snap_a0 = snap(db, Attachment, a0_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a0_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a0_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a0_id) == snap_a0
    # Then 5
    assert counts(db) == before


# [claude] ATSV-CF-13
def test_atsv_cf_13__a_w2_attachment_is_not_found(db, S):
    """ATSV-CF-13 — a W2 attachment is not found.
    Rules: confirm_upload R4; HR-16"""
    A2 = att(db, S, "pid-2", where="W2")
    link(db, S, A2, "scratch", 1)
    commit_point(db)
    a2_id = A2.id
    snap_a2 = snap(db, Attachment, a2_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a2_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a2_id) == snap_a2
    # Then 5
    assert counts(db) == before


# [claude] ATSV-CF-14
def test_atsv_cf_14__a_soft_deleted_attachment_is_not_found(db, S):
    """ATSV-CF-14 — a soft-deleted attachment is not found.
    Rules: confirm_upload R4"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", gone=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] ATSV-CF-15
@X2096
def test_atsv_cf_15__cloudinary_not_configured_passes_through_unchanged_nothing_written(
    db, S, cl
):
    """ATSV-CF-15 — Cloudinary not configured passes through unchanged; nothing written.
    Rules: confirm_upload R4 [BUG-2096]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.side_effect = CloudinaryNotConfiguredError("not set")
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == "not set"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before


# [claude] ATSV-CF-16
def test_atsv_cf_16__a_failing_commit_after_a_good_confirm_leaves_the_attachment_pending(
    db, S
):
    """ATSV-CF-16 — a failing commit after a good confirm leaves the attachment pending.
    Rules: confirm_upload R5, TC4"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.confirm_upload(
                db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, Attachment, a1_id)
    assert row.upload_status == "pending"
    assert row.file_url is None
    # Then 4
    assert counts(db) == before


# [claude] ATSV-CF-17
def test_atsv_cf_17__a_failing_reread_after_the_commit_leaves_the_attachment_ready(
    db, S
):
    """ATSV-CF-17 — a failing re-read after the commit leaves the attachment ready.
    Rules: confirm_upload R5, TC5"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh_after_commit(db):
            svc.confirm_upload(
                db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, Attachment, a1_id).upload_status == "ready"
    # Then 3
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "ready"


# [claude] ATSV-CF-18
@X2091
def test_atsv_cf_18__an_attachment_of_a_private_project_the_caller_may_not_open_is_not_found(
    db, S, cl
):
    """ATSV-CF-18 — an attachment of a private project the caller may not open is not found.
    Rules: confirm_upload R1 [BUG-2091]; PR-3, PR-5 (performed_by is the caller)"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl_untouched(cl) == UNTOUCHED


# [claude] ATSV-CF-19
@X2091
def test_atsv_cf_19__membership_of_another_private_project_does_not_open_this_attachment(
    db, S
):
    """ATSV-CF-19 — membership of another private project does not open this attachment.
    Rules: confirm_upload R1 [BUG-2091]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before


# [claude] ATSV-CF-20
def test_atsv_cf_20__a_project_member_confirms_the_private_projects_attachment(db, S):
    """ATSV-CF-20 — a project member confirms the private project's attachment.
    Rules: confirm_upload R1; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    result = svc.confirm_upload(
        db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
    )

    # Then 1
    assert result.upload_status == "ready"
    # Then 2
    db.rollback()
    assert reread(db, Attachment, a1_id).upload_status == "ready"
    # Then 3
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "ready"
    assert ledger[0].performed_by == S.UG.id


# [claude] ATSV-CF-21
@X2095
def test_atsv_cf_21__the_failure_records_commit_also_commits_an_unrelated_pending_row(
    db, S, cl
):
    """ATSV-CF-21 — the failure record's commit also commits an unrelated pending row.
    Rules: confirm_upload R3a [BUG-2095]; HR-13"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    cl.gr.side_effect = RuntimeError("boom")
    commit_point(db)
    a1_id = A1.id
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        svc.confirm_upload(
            db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
        )
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
    assert reread(db, Attachment, a1_id).upload_status == "failed"


# [claude] ATSV-CF-22
def test_atsv_cf_22__the_no_public_id_refusal_discards_an_unrelated_pending_row(db, S):
    """ATSV-CF-22 — the no-public_id refusal discards an unrelated pending row.
    Rules: confirm_upload R3b, TC3"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", public_id=None)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    before = counts(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        with spies(db) as (_cm, rb):
            svc.confirm_upload(
                db, workspace_id=S.W1.id, attachment_id=a1_id, performed_by=S.UG.id
            )
    # Then 2
    assert str(exc.value) == "Attachment has no public_id."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# AttachmentService.list_attachments
# --------------------------------------------------------------------------- #


# [claude] ATSV-L-01
def test_atsv_l_01__the_records_ready_live_attachments_the_used_places_and_the_maximum(
    db, S
):
    """ATSV-L-01 — the record's ready live attachments, the used places and the maximum.
    Rules: list_attachments R1, R3, R4"""
    M1 = mach(db, S, "Lathe")
    R1 = att(db, S, "r-1", ready=True)
    link(db, S, R1, "machine", M1)
    R2 = att(db, S, "r-2", ready=True)
    link(db, S, R2, "machine", M1)
    R3 = att(db, S, "r-3", ready=True)
    link(db, S, R3, "machine", M1)
    P4 = att(db, S, "p-4")
    link(db, S, P4, "machine", M1)
    G5 = att(db, S, "g-5", ready=True, gone=True)
    link(db, S, G5, "machine", M1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert type(result).__name__ == "AttachmentListResponse"
    # Then 2
    assert ids(result) == {R1.id, R2.id, R3.id}
    # Then 3
    assert all(lk(i) == [("machine", M1.id)] for i in result.items)
    # Then 4
    assert all(i.urls.preview_url == BSU for i in result.items)
    # Then 5
    assert result.slot_count == 4
    # Then 6
    assert result.max_per_entity == 25


# [claude] ATSV-L-02
def test_atsv_l_02__links_of_the_same_record_id_in_w0_and_w2_are_neither_listed_nor_counted(
    db, S
):
    """ATSV-L-02 — links of the same record id in W0 and W2 are neither listed nor counted.
    Rules: list_attachments R1, R3; HR-16"""
    M1 = mach(db, S, "Lathe")
    A0 = att(db, S, "w0-1", where="W0", ready=True)
    link(db, S, A0, "machine", M1.id)
    A1 = att(db, S, "w1-1", ready=True)
    link(db, S, A1, "machine", M1)
    A2 = att(db, S, "w2-1", where="W2", ready=True)
    link(db, S, A2, "machine", M1.id)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}
    # Then 2
    assert result.slot_count == 1


# [claude] ATSV-L-03
def test_atsv_l_03__other_records_and_the_same_id_under_another_type_do_not_count(
    db, S
):
    """ATSV-L-03 — other records with a lower and a higher id, and the same id under another type, do not count.
    Rules: list_attachments R1, R3"""
    MA = mach(db, S, "Alpha", id=XID(1))
    M1 = mach(db, S, "Lathe", id=XID(2))
    MB = mach(db, S, "Beta", id=XID(3))
    I1 = item(db, S, "Bolt", "B-1", id=XID(2))
    AA = att(db, S, "a-1", ready=True)
    link(db, S, AA, "machine", MA)
    A1 = att(db, S, "m-1", ready=True)
    link(db, S, A1, "machine", M1)
    AB = att(db, S, "b-1", ready=True)
    link(db, S, AB, "machine", MB)
    AI = att(db, S, "i-1", ready=True)
    link(db, S, AI, "item", I1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=XID(2),
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}
    # Then 2
    assert result.slot_count == 1


# [claude] ATSV-L-04
def test_atsv_l_04__slot_count_does_not_depend_on_the_page(db, S):
    """ATSV-L-04 — slot_count does not depend on the page.
    Rules: list_attachments R3"""
    M1 = mach(db, S, "Lathe")
    FL = fill(db, S, M1, 3, "ready")
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=2,
    )

    # Then 1
    assert len(result.items) == 2
    # Then 2
    assert ids(result) <= {a.id for a in FL}
    # Then 3
    assert result.slot_count == 3


# [claude] ATSV-L-05
def test_atsv_l_05__the_default_page_holds_100_items(db, S, monkeypatch):
    """ATSV-L-05 — the default page holds 100 items.
    Rules: list_attachments R1 (default limit=100)"""
    setting(monkeypatch, "MAX_ATTACHMENTS_PER_ENTITY", 500)
    M1 = mach(db, S, "Lathe")
    fill(db, S, M1, 101, "ready")
    commit_point(db)
    result = la(
        db, S.UG, workspace_id=S.W1.id, entity_type=ET("machine"), entity_id=M1.id
    )

    # Then 1
    assert len(result.items) == 100
    # Then 2
    assert result.slot_count == 101
    # Then 3
    assert result.max_per_entity == 500


# [claude] ATSV-L-06
def test_atsv_l_06__max_per_entity_is_read_from_settings_at_the_call(
    db, S, monkeypatch
):
    """ATSV-L-06 — max_per_entity is read from settings at the call.
    Rules: list_attachments R4"""
    setting(monkeypatch, "MAX_ATTACHMENTS_PER_ENTITY", 7)
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert result.max_per_entity == 7
    # Then 2
    assert result.items == []
    assert result.slot_count == 0


# [claude] ATSV-L-07
def test_atsv_l_07__failed_attachments_are_not_listed(db, S):
    """ATSV-L-07 — failed attachments are not listed.
    Rules: list_attachments R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "machine", M1)
    AF = att(db, S, "f-1", failed=True)
    link(db, S, AF, "machine", M1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}


# [claude] ATSV-L-08
@X1434
def test_atsv_l_08__failed_attachments_do_not_use_a_place(db, S):
    """ATSV-L-08 — failed attachments do not use a place.
    Rules: list_attachments R3 [BUG-1434]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "machine", M1)
    AF = att(db, S, "f-1", failed=True)
    link(db, S, AF, "machine", M1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}
    # Then 2
    assert result.slot_count == 1


# [claude] ATSV-L-09
def test_atsv_l_09__a_list_neither_commits_nor_rolls_back_pending_changes_stay_pending(
    db, S
):
    """ATSV-L-09 — a list neither commits nor rolls back; pending changes stay pending.
    Rules: list_attachments R6, TC6"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    w1_id, m1_id, a1_id = S.W1.id, M1.id, A1.id
    x_id = pending_x(db, S)
    pending_edit(S)
    with spies(db) as (cm, rb):
        result = la(
            db,
            S.UG,
            workspace_id=w1_id,
            entity_type=ET("machine"),
            entity_id=m1_id,
            skip=0,
            limit=1000,
        )

    # Then 1
    assert ids(result) == {a1_id}
    # Then 2
    assert cm.called is False
    assert rb.called is False
    # Then 3
    assert S.F9 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert x_count(db, x_id) == 1
    # Then 5
    db.rollback()
    assert x_count(db, x_id) == 0


# [claude] ATSV-L-10
def test_atsv_l_10__a_negative_skip_raises_dataerror_without_a_rollback(db, S):
    """ATSV-L-10 — a negative skip raises DataError without a rollback.
    Rules: list_attachments R6"""
    M1 = mach(db, S, "Lathe")
    commit_point(db)
    w1_id, m1_id, f9_id = S.W1.id, M1.id, S.F9.id
    pending_edit(S)

    # Then 1
    with pytest.raises(DataError):
        with spies(db) as (cm, rb):
            with db.begin_nested():
                la(
                    db,
                    S.UG,
                    workspace_id=w1_id,
                    entity_type=ET("machine"),
                    entity_id=m1_id,
                    skip=-1,
                    limit=100,
                )
    # Then 2
    assert cm.called is False
    assert rb.called is False
    # Then 3
    assert reread(db, Factory, f9_id).name == "Factory Edited"
    # Then 4
    db.rollback()
    assert reread(db, Factory, f9_id).name == "Factory Nine"


# [claude] ATSV-L-11
@X2201
def test_atsv_l_11__the_links_of_all_listed_attachments_are_read_together(db, S):
    """ATSV-L-11 — the links of all listed attachments are read together.
    Rules: list_attachments R5 [BUG-2201]"""
    M1 = mach(db, S, "Lathe")
    fill(db, S, M1, 5, "ready")
    with recorder(db) as stmts:
        commit_point(db)
        result = la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("machine"),
            entity_id=M1.id,
            skip=0,
            limit=1000,
        )

    # Then 1
    assert len(result.items) == 5
    assert all(lk(i) == [("machine", M1.id)] for i in result.items)
    # Then 2
    assert link_stmts(stmts) <= 3


# [claude] ATSV-L-12
@X2200
def test_atsv_l_12__an_unknown_record_is_not_found(db, S):
    """ATSV-L-12 — an unknown record is not found.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("machine"),
            entity_id=MISSING,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("machine", MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-13
@X2200
def test_atsv_l_13__a_deleted_machines_files_are_not_listed(db, S, cl):
    """ATSV-L-13 — a deleted machine's files are not listed.
    Rules: list_attachments R1a [BUG-2200]; PR-1, HR-4"""
    M1 = mach(db, S, "Lathe", deleted=True)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("machine"),
            entity_id=M1.id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("machine", M1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert cl.bsu.called is False


# [claude] ATSV-L-14
@X2200
def test_atsv_l_14__a_deleted_projects_files_are_not_listed(db, S):
    """ATSV-L-14 — a deleted project's files are not listed.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    P1 = proj(db, S, "Tender", deleted=True)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("project"),
            entity_id=P1.id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("project", P1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-15
@X2200
def test_atsv_l_15__a_component_of_a_deleted_project_is_not_found(db, S):
    """ATSV-L-15 — a component of a deleted project is not found.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    P1 = proj(db, S, "Tender", deleted=True)
    C1 = comp(db, P1, "Roof")
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project_component", C1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("project_component"),
            entity_id=C1.id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("project_component", C1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-16
@X2200
def test_atsv_l_16__a_w0_machine_is_not_found_from_w1(db, S):
    """ATSV-L-16 — a W0 machine is not found from W1.
    Rules: list_attachments R1a [BUG-2200]; HR-16"""
    M0 = mach(db, S, "Lathe", where="W0")
    A0 = att(db, S, "w0-1", where="W0", ready=True)
    link(db, S, A0, "machine", M0)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("machine"),
            entity_id=M0.id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("machine", M0.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-17
@X2200
def test_atsv_l_17__a_w2_machine_is_not_found_from_w1(db, S):
    """ATSV-L-17 — a W2 machine is not found from W1.
    Rules: list_attachments R1a [BUG-2200]; HR-16"""
    M2 = mach(db, S, "Lathe", where="W2")
    A2 = att(db, S, "w2-1", where="W2", ready=True)
    link(db, S, A2, "machine", M2)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("machine"),
            entity_id=M2.id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("machine", M2.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-18
@X2200
def test_atsv_l_18__a_project_id_that_exists_only_as_a_machine_is_not_found(db, S):
    """ATSV-L-18 — a project id that exists only as a machine is not found, though links name it.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    mach(db, S, "Lathe", id=XID(4))
    assert db.get(Project, XID(4)) is None
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project", XID(4))
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("project"),
            entity_id=XID(4),
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("project", XID(4))
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-19
def test_atsv_l_19__scratch_passes_with_any_id(db, S):
    """ATSV-L-19 — scratch passes with any id.
    Rules: list_attachments R1a (scratch)"""
    A1 = att(db, S, "s-1", ready=True)
    link(db, S, A1, "scratch", 77)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("scratch"),
        entity_id=77,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}
    # Then 2
    assert result.slot_count == 1


# [claude] ATSV-L-20
@X1870
def test_atsv_l_20__a_private_project_the_caller_may_not_open_is_not_found(db, S, cl):
    """ATSV-L-20 — a private project the caller may not open is not found.
    Rules: list_attachments R2 [BUG-1870]; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_attachments(
            db,
            workspace_id=S.W1.id,
            entity_type=ET("project"),
            entity_id=P1.id,
            skip=0,
            limit=100,
            user_id=S.UG.id,
        )
    # Then 2
    assert str(exc.value) == NF("project", P1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert cl.bsu.called is False


# [claude] ATSV-L-21
@X1870
def test_atsv_l_21__membership_of_another_private_project_does_not_open_this_one(db, S):
    """ATSV-L-21 — membership of another private project does not open this one.
    Rules: list_attachments R2 [BUG-1870]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_attachments(
            db,
            workspace_id=S.W1.id,
            entity_type=ET("project"),
            entity_id=P1.id,
            skip=0,
            limit=100,
            user_id=S.UG.id,
        )
    # Then 2
    assert str(exc.value) == NF("project", P1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-22
@X1950
def test_atsv_l_22__an_owner_role_held_only_in_w0_does_not_open_another_members_w1_ticket(
    db, S
):
    """ATSV-L-22 — an owner role held only in W0 does not open another member's W1 ticket.
    Rules: list_attachments R2 [BUG-1950]; PR-2, PR-5 (grant held in a different workspace)"""
    member(db, S.UG, "owner", S.W0)
    T1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "support_ticket", T1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_attachments(
            db,
            workspace_id=S.W1.id,
            entity_type=ET("support_ticket"),
            entity_id=T1.id,
            skip=0,
            limit=100,
            user_id=S.UG.id,
        )
    # Then 2
    assert str(exc.value) == NF("support_ticket", T1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-23
def test_atsv_l_23__a_project_member_lists_the_private_projects_files(db, S):
    """ATSV-L-23 — a project member lists the private project's files.
    Rules: list_attachments R1, R2; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("project"),
        entity_id=P1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}
    # Then 2
    assert result.slot_count == 1


# [claude] ATSV-L-24
def test_atsv_l_24__the_tickets_creator_lists_its_files(db, S):
    """ATSV-L-24 — the ticket's creator lists its files.
    Rules: list_attachments R1, R2; PR-2"""
    T1 = ticket(db, S, "HT-1", created_by=S.UG.id)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "support_ticket", T1)
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("support_ticket"),
        entity_id=T1.id,
        skip=0,
        limit=1000,
    )

    # Then 1
    assert ids(result) == {A1.id}


# [claude] ATSV-L-25
@X2200
def test_atsv_l_25__a_deleted_work_orders_files_are_not_listed(db, S):
    """ATSV-L-25 — a deleted work order's files are not listed.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    WO1 = wo(db, S, "WO-1", deleted=True)
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "work_order", WO1)
    commit_point(db)
    wo1_id = WO1.id

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("work_order"),
            entity_id=wo1_id,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("work_order", wo1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-26
@X2200
def test_atsv_l_26__an_unknown_purchase_order_is_not_found_though_a_link_names_it(
    db, S
):
    """ATSV-L-26 — an unknown purchase order (no soft delete) is not found, though a link names it.
    Rules: list_attachments R1a [BUG-2200]; PR-1"""
    A1 = att(db, S, "r-1", ready=True)
    link(db, S, A1, "purchase_order", MISSING)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        la(
            db,
            S.UG,
            workspace_id=S.W1.id,
            entity_type=ET("purchase_order"),
            entity_id=MISSING,
            skip=0,
            limit=100,
        )
    # Then 2
    assert str(exc.value) == NF("purchase_order", MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-L-27
def test_atsv_l_27__the_default_skip_is_0(db, S):
    """ATSV-L-27 — the default skip is 0.
    Rules: list_attachments R1 (default skip=0)"""
    M1 = mach(db, S, "Lathe")
    FL = fill(db, S, M1, 3, "ready")
    commit_point(db)
    result = la(
        db,
        S.UG,
        workspace_id=S.W1.id,
        entity_type=ET("machine"),
        entity_id=M1.id,
        limit=1000,
    )

    # Then 1
    assert len(result.items) == 3
    # Then 2
    assert ids(result) == {a.id for a in FL}


# --------------------------------------------------------------------------- #
# AttachmentService.get_attachment
# --------------------------------------------------------------------------- #


# [claude] ATSV-G-01
def test_atsv_g_01__a_ready_attachment_is_answered_with_its_urls_neighbours_are_not(
    db, S
):
    """ATSV-G-01 — a ready attachment is answered with its URLs; neighbours by id are not.
    Rules: get_attachment R1"""
    M1 = mach(db, S, "Lathe")
    AL = att(db, S, "pid-l", ready=True, file_name="low.jpg")
    link(db, S, AL, "machine", M1)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    AH = att(db, S, "pid-h", ready=True, file_name="high.jpg")
    link(db, S, AH, "machine", M1)
    commit_point(db)
    result = ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id)

    # Then 1
    assert type(result).__name__ == "AttachmentResponse"
    assert result.id == A1.id
    # Then 2
    assert result.file_name == "photo.jpg"
    assert result.upload_status == "ready"
    assert result.public_id == "pid-1"
    # Then 3
    assert result.urls.preview_url == BSU
    assert result.urls.download_url == BSU
    # Then 4
    assert lk(result) == [("machine", M1.id)]


# [claude] ATSV-G-02
def test_atsv_g_02__a_pending_attachment_is_answered_without_urls(db, S, cl):
    """ATSV-G-02 — a pending attachment is answered without URLs.
    Rules: get_attachment R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id)

    # Then 1
    assert result.id == A1.id
    assert result.upload_status == "pending"
    # Then 2
    assert result.urls.thumb_url is None
    assert result.urls.preview_url is None
    assert result.urls.download_url is None
    # Then 3
    assert cl.bsu.called is False


# [claude] ATSV-G-03
def test_atsv_g_03__a_failed_attachment_is_answered_without_urls(db, S):
    """ATSV-G-03 — a failed attachment is answered without URLs.
    Rules: get_attachment R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", failed=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id)

    # Then 1
    assert result.id == A1.id
    assert result.upload_status == "failed"
    # Then 2
    assert result.urls.preview_url is None


# [claude] ATSV-G-04
def test_atsv_g_04__an_unknown_id_is_not_found(db, S):
    """ATSV-G-04 — an unknown id is not found.
    Rules: get_attachment R1a"""
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        ga(db, S.UG, workspace_id=S.W1.id, attachment_id=MISSING)
    # Then 2
    assert str(exc.value) == NFA(MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-05
def test_atsv_g_05__id_0_is_not_found(db, S):
    """ATSV-G-05 — id 0 is not found.
    Rules: get_attachment R1a"""
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        ga(db, S.UG, workspace_id=S.W1.id, attachment_id=0)
    # Then 2
    assert str(exc.value) == NFA(0)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-06
def test_atsv_g_06__a_soft_deleted_attachment_is_not_found(db, S):
    """ATSV-G-06 — a soft-deleted attachment is not found.
    Rules: get_attachment R1a; HR-4"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, gone=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id)
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-07
def test_atsv_g_07__a_w0_attachment_is_not_found(db, S):
    """ATSV-G-07 — a W0 attachment is not found.
    Rules: get_attachment R1a; HR-16"""
    A0 = att(db, S, "pid-0", where="W0", ready=True)
    link(db, S, A0, "scratch", 1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A0.id)
    # Then 2
    assert str(exc.value) == NFA(A0.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-08
def test_atsv_g_08__a_w2_attachment_is_not_found(db, S):
    """ATSV-G-08 — a W2 attachment is not found.
    Rules: get_attachment R1a; HR-16"""
    A2 = att(db, S, "pid-2", where="W2", ready=True)
    link(db, S, A2, "scratch", 1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A2.id)
    # Then 2
    assert str(exc.value) == NFA(A2.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-09
def test_atsv_g_09__a_read_neither_commits_nor_rolls_back_pending_changes_stay(db, S):
    """ATSV-G-09 — a read neither commits nor rolls back; pending changes stay.
    Rules: get_attachment R3, TC6"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    w1_id, a1_id = S.W1.id, A1.id
    x_id = pending_x(db, S)
    pending_edit(S)
    with spies(db) as (cm, rb):
        result = ga(db, S.UG, workspace_id=w1_id, attachment_id=a1_id)

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert cm.called is False
    assert rb.called is False
    # Then 3
    assert S.F9 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert x_count(db, x_id) == 1
    # Then 5
    db.rollback()
    assert x_count(db, x_id) == 0


# [claude] ATSV-G-10
def test_atsv_g_10__a_not_found_refusal_does_not_roll_back_the_callers_pending_edit(
    db, S
):
    """ATSV-G-10 — a not-found refusal does not roll back the caller's pending edit.
    Rules: get_attachment R1a, R3, TC6"""
    commit_point(db)
    w1_id = S.W1.id
    pending_edit(S)

    # Then 1
    with pytest.raises(AttachmentNotFoundError):
        with spies(db) as (cm, rb):
            ga(db, S.UG, workspace_id=w1_id, attachment_id=MISSING)
    # Then 2
    assert rb.called is False
    assert cm.called is False
    # Then 3
    assert S.F9 in db.dirty
    assert len(db.dirty) == 1


# [claude] ATSV-G-11
@X2091
def test_atsv_g_11__an_attachment_of_a_private_project_the_caller_may_not_open_is_not_found(
    db, S, cl
):
    """ATSV-G-11 — an attachment of a private project the caller may not open is not found.
    Rules: get_attachment R2 [BUG-2091]; PR-3, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_attachment(
            db, workspace_id=S.W1.id, attachment_id=A1.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert cl.bsu.called is False


# [claude] ATSV-G-12
@X2091
def test_atsv_g_12__membership_of_another_private_project_does_not_open_this_attachment(
    db, S
):
    """ATSV-G-12 — membership of another private project does not open this attachment.
    Rules: get_attachment R2 [BUG-2091]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_attachment(
            db, workspace_id=S.W1.id, attachment_id=A1.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-13
@X2091
def test_atsv_g_13__an_attachment_whose_only_link_is_filed_under_w2_is_not_found(db, S):
    """ATSV-G-13 — an attachment whose only link is filed under W2 is not found.
    Rules: get_attachment R2 [BUG-2091]; PR-3 (only own-workspace links count)"""
    M2 = mach(db, S, "Lathe", where="W2")
    A1 = att(db, S, "pid-1", ready=True)
    db.add(
        AttachmentLink(
            workspace_id=S.W2.id,
            attachment_id=A1.id,
            entity_type="machine",
            entity_id=M2.id,
            linked_by=S.U1.id,
        )
    )
    db.flush()
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_attachment(
            db, workspace_id=S.W1.id, attachment_id=A1.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-14
@X2091
def test_atsv_g_14__a_link_to_a_project_id_that_exists_only_as_a_machine_hides_the_attachment(
    db, S
):
    """ATSV-G-14 — a link to a project id that exists only as a machine hides the attachment.
    Rules: get_attachment R2 [BUG-2091]; PR-1, PR-3"""
    mach(db, S, "Lathe", id=XID(5))
    assert db.get(Project, XID(5)) is None
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", XID(5))
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_attachment(
            db, workspace_id=S.W1.id, attachment_id=A1.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-G-15
def test_atsv_g_15__a_project_member_reads_the_private_projects_attachment(db, S):
    """ATSV-G-15 — a project member reads the private project's attachment.
    Rules: get_attachment R1, R2; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)
    result = ga(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id)

    # Then 1
    assert result.id == A1.id
    assert lk(result) == [("project", P1.id)]


# --------------------------------------------------------------------------- #
# AttachmentService.get_pdf_page_image
# --------------------------------------------------------------------------- #


# [claude] ATSV-PG-01
def test_atsv_pg_01__a_ready_pdf_answers_the_page_image(db, S, cl):
    """ATSV-PG-01 — a ready PDF answers the page image.
    Rules: get_pdf_page_image R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, pdf=True, page_count=5)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    result = pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=2)

    # Then 1
    assert type(result).__name__ == "AttachmentPdfPageResponse"
    # Then 2
    assert result.url == BSU
    assert result.page == 2
    assert result.page_count == 5
    # Then 3
    assert cl.bsu.call_count == 1
    assert kw(cl.bsu)["public_id"] == "pid-1"
    assert kw(cl.bsu)["fmt"] == "jpg"
    # Then 4
    assert kw(cl.bsu)["transformation"] == [
        {
            "page": 2,
            "fetch_format": "jpg",
            "quality": "auto:good",
            "width": 1600,
            "crop": "limit",
            "density": 200,
        }
    ]


# [claude] ATSV-PG-02
def test_atsv_pg_02__page_0_reaches_the_caller_as_the_managers_validation_error(db, S):
    """ATSV-PG-02 — page 0 reaches the caller as the manager's validation error.
    Rules: get_pdf_page_image R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=0)
    # Then 2
    assert str(exc.value) == "Page number must be at least 1."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-03
def test_atsv_pg_03__a_pending_pdf_reaches_the_caller_as_not_ready(db, S):
    """ATSV-PG-03 — a pending PDF reaches the caller as "not ready".
    Rules: get_pdf_page_image R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", pdf=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=1)
    # Then 2
    assert str(exc.value) == "Attachment is not ready."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-04
def test_atsv_pg_04__a_ready_image_reaches_the_caller_as_not_a_pdf(db, S):
    """ATSV-PG-04 — a ready image reaches the caller as "not a PDF".
    Rules: get_pdf_page_image R1"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=1)
    # Then 2
    assert str(exc.value) == "Attachment is not a PDF."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-05
def test_atsv_pg_05__an_unknown_id_is_not_found(db, S):
    """ATSV-PG-05 — an unknown id is not found.
    Rules: get_pdf_page_image R1"""
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        pg(db, S.UG, workspace_id=S.W1.id, attachment_id=MISSING, page=1)
    # Then 2
    assert str(exc.value) == NFA(MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-06
def test_atsv_pg_06__cloudinary_not_configured_reaches_the_caller_unchanged(
    db, S, monkeypatch
):
    """ATSV-PG-06 — Cloudinary not configured reaches the caller unchanged.
    Rules: get_pdf_page_image R1"""
    setting(monkeypatch, "CLOUDINARY_CLOUD_NAME", "")
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)

    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=1)
    # Then 2
    assert str(exc.value) == "Cloudinary is not configured."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-07
def test_atsv_pg_07__a_page_read_neither_commits_nor_rolls_back_pending_changes_stay(
    db, S
):
    """ATSV-PG-07 — a page read neither commits nor rolls back; pending changes stay.
    Rules: get_pdf_page_image R3, TC6"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    w1_id, a1_id = S.W1.id, A1.id
    x_id = pending_x(db, S)
    pending_edit(S)
    with spies(db) as (cm, rb):
        result = pg(db, S.UG, workspace_id=w1_id, attachment_id=a1_id, page=1)

    # Then 1
    assert result.page == 1
    # Then 2
    assert cm.called is False
    assert rb.called is False
    # Then 3
    assert S.F9 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert x_count(db, x_id) == 1


# [claude] ATSV-PG-08
@X2091
def test_atsv_pg_08__a_private_projects_pdf_the_caller_may_not_open_is_not_found(
    db, S, cl
):
    """ATSV-PG-08 — a private project's PDF the caller may not open is not found.
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_pdf_page_image(
            db, workspace_id=S.W1.id, attachment_id=A1.id, page=1, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert cl.bsu.called is False


# [claude] ATSV-PG-09
@X2091
def test_atsv_pg_09__a_hidden_pdf_answers_not_found_before_the_page_check(db, S):
    """ATSV-PG-09 — a hidden PDF answers not found before the page check.
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-4"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_pdf_page_image(
            db, workspace_id=S.W1.id, attachment_id=A1.id, page=0, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-10
@X2091
def test_atsv_pg_10__membership_of_another_private_project_does_not_open_this_pdf(
    db, S
):
    """ATSV-PG-10 — membership of another private project does not open this PDF.
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.get_pdf_page_image(
            db, workspace_id=S.W1.id, attachment_id=A1.id, page=1, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(A1.id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] ATSV-PG-11
def test_atsv_pg_11__a_project_member_gets_the_private_projects_pdf_page(db, S):
    """ATSV-PG-11 — a project member gets the private project's PDF page.
    Rules: get_pdf_page_image R1, R2; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "pid-1", ready=True, pdf=True, page_count=3)
    link(db, S, A1, "project", P1)
    commit_point(db)
    result = pg(db, S.UG, workspace_id=S.W1.id, attachment_id=A1.id, page=3)

    # Then 1
    assert result.url == BSU
    assert result.page == 3
    assert result.page_count == 3


# [claude] ATSV-PG-12
def test_atsv_pg_12__an_error_neither_rolls_back_nor_commits_the_pending_edit_stays(
    db, S
):
    """ATSV-PG-12 — an error neither rolls back nor commits; the caller's pending edit stays.
    Rules: get_pdf_page_image R1, R3, TC6"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, pdf=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    w1_id, a1_id = S.W1.id, A1.id
    pending_edit(S)

    # Then 1
    with pytest.raises(AttachmentValidationError):
        with spies(db) as (cm, rb):
            pg(db, S.UG, workspace_id=w1_id, attachment_id=a1_id, page=0)
    # Then 2
    assert rb.called is False
    assert cm.called is False
    # Then 3
    assert S.F9 in db.dirty
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# AttachmentService.delete_attachment
# --------------------------------------------------------------------------- #


# [claude] ATSV-D-01
def test_atsv_d_01__delete_soft_deletes_commits_and_answers_the_reread_row(db, S):
    """ATSV-D-01 — delete soft-deletes, commits, and answers the re-read row.
    Rules: delete_attachment R1, TC1, TC2"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert type(result).__name__ == "AttachmentResponse"
    assert result.id == a1_id
    # Then 2
    assert result.file_name == "photo.jpg"
    assert lk(result) == [("machine", M1.id)]
    # Then 3
    db.rollback()
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id
    assert row.deleted_at is not None
    # Then 4
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "deleted"
    assert ledger[0].performed_by == S.UG.id
    # Then 5
    assert events_of(db, M1) == [("attachment_removed", "Removed photo.jpg", S.UG.id)]
    # Then 6
    assert len(links_of(db, a1_id)) == 1


# [claude] ATSV-D-02
def test_atsv_d_02__the_cloudinary_file_of_a_ready_attachment_is_deleted_by_its_stored_id(
    db, S, cl
):
    """ATSV-D-02 — the Cloudinary file of a ready attachment is deleted by its stored id.
    Rules: delete_attachment R1, R4 (part that holds today and after)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert cl.dr.call_count == 1
    # Then 3
    assert kw(cl.dr)["public_id"] == "pid-1"
    assert kw(cl.dr)["resource_type"] == "image"
    assert kw(cl.dr)["delivery_type"] == "authenticated"


# [claude] ATSV-D-03
def test_atsv_d_03__an_unknown_id_not_found_rolled_back_other_pending_changes_discarded(
    db, S, cl
):
    """ATSV-D-03 — an unknown id: not found, rolled back, other pending changes discarded.
    Rules: delete_attachment R2, R3, TC3"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_attachment(
                db, workspace_id=S.W1.id, attachment_id=MISSING, deleted_by=S.UG.id
            )
    # Then 2
    assert str(exc.value) == NFA(MISSING)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 7
    assert counts(db) == before
    # Then 8
    assert cl.dr.called is False


# [claude] ATSV-D-04
def test_atsv_d_04__a_w0_attachment_is_not_found_nothing_written(db, S, cl):
    """ATSV-D-04 — a W0 attachment is not found; nothing written.
    Rules: delete_attachment R2; HR-16"""
    A0 = att(db, S, "pid-0", where="W0", ready=True)
    link(db, S, A0, "scratch", 1)
    commit_point(db)
    a0_id = A0.id
    snap_a0 = snap(db, Attachment, a0_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a0_id, deleted_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a0_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a0_id) == snap_a0
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl.dr.called is False


# [claude] ATSV-D-05
def test_atsv_d_05__a_w2_attachment_is_not_found_nothing_written(db, S, cl):
    """ATSV-D-05 — a W2 attachment is not found; nothing written.
    Rules: delete_attachment R2; HR-16"""
    A2 = att(db, S, "pid-2", where="W2", ready=True)
    link(db, S, A2, "scratch", 1)
    commit_point(db)
    a2_id = A2.id
    snap_a2 = snap(db, Attachment, a2_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a2_id, deleted_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a2_id) == snap_a2
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl.dr.called is False


# [claude] ATSV-D-06
@X2097
def test_atsv_d_06__an_already_deleted_attachment_is_not_found_nothing_written(
    db, S, cl
):
    """ATSV-D-06 — an already deleted attachment is not found; nothing written.
    Rules: delete_attachment R2 [BUG-2097]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, gone=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl.dr.called is False


# [claude] ATSV-D-07
def test_atsv_d_07__a_database_error_rolls_back_the_attachment_stays_live(db, S):
    """ATSV-D-07 — a database error rolls back: the attachment stays live.
    Rules: delete_attachment R3, TC3"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    before = counts(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(IntegrityError):
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=MISSING
        )
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is False
    assert row.deleted_by is None
    assert row.upload_status == "ready"
    # Then 5
    assert counts(db) == before
    # Then 6
    assert db.execute(text("SELECT 1")).scalar() == 1


# [claude] ATSV-D-08
def test_atsv_d_08__a_failing_commit_leaves_the_attachment_live_and_ready(db, S):
    """ATSV-D-08 — a failing commit leaves the attachment live and ready.
    Rules: delete_attachment R3, R4, TC4"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    before = counts(db)
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_attachment(
                db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is False
    assert row.upload_status == "ready"
    assert row.public_id == "pid-1"
    # Then 4
    assert counts(db) == before


# [claude] ATSV-D-09
@X2202
def test_atsv_d_09__a_failing_commit_never_deletes_the_cloudinary_file(db, S, cl):
    """ATSV-D-09 — a failing commit never deletes the Cloudinary file.
    Rules: delete_attachment R4 [BUG-2202]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db):
            svc.delete_attachment(
                db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert reread(db, Attachment, a1_id).is_deleted is False
    # Then 3
    assert cl.dr.called is False


# [claude] ATSV-D-10
@X2202
def test_atsv_d_10__on_success_the_commit_comes_before_the_cloudinary_delete(db, S, cl):
    """ATSV-D-10 — on success the commit comes before the Cloudinary delete.
    Rules: delete_attachment R4 [BUG-2202]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    with order_log(db, cl) as order:
        result = svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
        )

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert order.count("dr") == 1
    assert "commit" in order
    # Then 3
    assert order.index("commit") < order.index("dr")


# [claude] ATSV-D-11
def test_atsv_d_11__a_failing_reread_after_the_commit_leaves_the_delete_saved(db, S):
    """ATSV-D-11 — a failing re-read after the commit leaves the delete saved.
    Rules: delete_attachment R3, TC5"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id, ug_id = A1.id, S.UG.id
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.delete_attachment(
                db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=ug_id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is True
    assert row.deleted_by == ug_id
    # Then 3
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "deleted"


# [claude] ATSV-D-12
@X2091
def test_atsv_d_12__an_attachment_of_a_private_project_the_caller_may_not_open_is_not_found(
    db, S, cl
):
    """ATSV-D-12 — an attachment of a private project the caller may not open is not found.
    Rules: delete_attachment R1, R2 [BUG-2091]; PR-3, PR-5 (deleted_by is the caller)"""
    P1 = proj(db, S, "Tender", private=True)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert cl.dr.called is False


# [claude] ATSV-D-13
@X2091
def test_atsv_d_13__membership_of_another_private_project_does_not_open_this_attachment(
    db, S
):
    """ATSV-D-13 — membership of another private project does not open this attachment.
    Rules: delete_attachment R2 [BUG-2091]; PR-2 (grant held on a different record)"""
    P1 = proj(db, S, "Tender", private=True)
    P2 = proj(db, S, "Bridge", private=True)
    pmem(db, S, P2, S.UG)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    snap_a1 = snap(db, Attachment, a1_id)
    before = counts(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_attachment(
            db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a1_id)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, Attachment, a1_id) == snap_a1
    # Then 5
    assert counts(db) == before


# [claude] ATSV-D-14
def test_atsv_d_14__a_project_member_deletes_the_private_projects_attachment(db, S):
    """ATSV-D-14 — a project member deletes the private project's attachment.
    Rules: delete_attachment R1; PR-2, PR-5"""
    P1 = proj(db, S, "Tender", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "project", P1)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    db.rollback()
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id


# [claude] ATSV-D-15
@X2099
def test_atsv_d_15__a_pending_attachments_file_is_deleted_after_the_commit(db, S, cl):
    """ATSV-D-15 — a pending attachment's file is deleted after the commit.
    Rules: delete_attachment R4 [BUG-2202] with manager R6 [BUG-2099]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1")
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    db.rollback()
    assert reread(db, Attachment, a1_id).is_deleted is True
    # Then 3
    assert cl.dr.call_count == 1
    assert kw(cl.dr)["public_id"] == "pid-1"


# [claude] ATSV-D-16
@X2099
def test_atsv_d_16__a_failed_attachments_file_is_deleted_after_the_commit(db, S, cl):
    """ATSV-D-16 — a failed attachment's file is deleted after the commit.
    Rules: delete_attachment R4 [BUG-2202] with manager R6 [BUG-2099]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", failed=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    db.rollback()
    assert reread(db, Attachment, a1_id).is_deleted is True
    # Then 3
    assert cl.dr.call_count == 1
    assert kw(cl.dr)["public_id"] == "pid-1"


# [claude] ATSV-D-17
def test_atsv_d_17__no_public_id_the_delete_is_saved_and_cloudinary_is_not_called(
    db, S, cl
):
    """ATSV-D-17 — no public_id: the delete is saved and Cloudinary is not called.
    Rules: delete_attachment R4 (manager R5, R6)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True, public_id=None)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id, ug_id = A1.id, S.UG.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=ug_id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    db.rollback()
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is True
    assert row.deleted_by == ug_id
    # Then 3
    assert cl.dr.called is False


# [claude] ATSV-D-18
def test_atsv_d_18__a_cloudinary_delete_error_is_swallowed_the_delete_is_saved(
    db, S, cl
):
    """ATSV-D-18 — a Cloudinary delete error is swallowed: the delete is saved and answered.
    Rules: delete_attachment R4a [BUG-2202] (part that holds today)"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    cl.dr.side_effect = RuntimeError("down")
    commit_point(db)
    a1_id, ug_id = A1.id, S.UG.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=ug_id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert cl.dr.call_count == 1
    # Then 3
    db.rollback()
    row = reread(db, Attachment, a1_id)
    assert row.is_deleted is True
    assert row.deleted_by == ug_id
    # Then 4
    ledger = ledger_of(db, a1_id)
    assert len(ledger) == 1
    assert ledger[0].transaction_type == "deleted"


# [claude] ATSV-D-19
@X2100
def test_atsv_d_19__a_cloudinary_delete_error_is_logged_as_a_warning_naming_the_file(
    db, S, cl, caplog
):
    """ATSV-D-19 — a Cloudinary delete error is logged as a WARNING naming the file.
    Rules: delete_attachment R4a [BUG-2202] with manager R7 [BUG-2100]"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    cl.dr.side_effect = RuntimeError("down")
    warnings_on(caplog)
    commit_point(db)
    a1_id = A1.id
    result = svc.delete_attachment(
        db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
    )

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert warned(caplog, "pid-1") is True


# [claude] ATSV-D-20
def test_atsv_d_20__the_file_is_deleted_even_when_the_reread_after_the_commit_fails(
    db, S, cl
):
    """ATSV-D-20 — the file is deleted even when the re-read after the commit fails.
    Rules: delete_attachment R4a [BUG-2202], R3, TC5"""
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "pid-1", ready=True)
    link(db, S, A1, "machine", M1)
    commit_point(db)
    a1_id = A1.id
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh_after_commit(db):
            svc.delete_attachment(
                db, workspace_id=S.W1.id, attachment_id=a1_id, deleted_by=S.UG.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert cl.dr.call_count == 1
    assert kw(cl.dr)["public_id"] == "pid-1"
    # Then 3
    db.rollback()
    assert reread(db, Attachment, a1_id).is_deleted is True
