"""Unit tests for app/managers/attachment_markup_manager.py.

Implements tests/unit/managers/attachment_markup_manager.cases.md (revision 2),
one test per card, in card order. Real Postgres session (`db` fixture), rolled
back after each test.

Nothing external is patched (the spec names no external; the stamp URL builder
of BUG-2117 makes no network call). Every test sets the Cloudinary / environment
settings of the Conventions on `app.core.config.settings` (autouse fixture).
The one race simulation is AMUP-PL-25 (BUG-2120): the markup DAO's
`get_for_user` is patched to return None. The commit spies of the "Rolled back"
cards wrap `db.commit`.

Every test that touches the database builds the Standing rows (fixture `S`,
attributes named as in the cards: `S.W1`, `S.UG`, `S.A1` ...). Given rows are
built by the helpers below, one flush per row. `# Then N` marks the checks of
the card's Then line N.
"""
import inspect
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.managers.attachment_manager import (
    AttachmentNotFoundError,
    AttachmentValidationError,
)
from app.managers.attachment_markup_manager import (
    AttachmentMarkupManager,
    attachment_markup_manager,
)
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink
from app.models.attachment_markup import AttachmentMarkup
from app.models.attachment_markup_event import AttachmentMarkupEvent
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.attachment_markup import MarkupPayload
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = attachment_markup_manager"
M = attachment_markup_manager

# Convention "MISSING"
MISSING = 999999999

# Conventions T0, T1, T2 (naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 1, 1, 10, 0, 0)  # noqa: DTZ001

# Convention "UNAV"
UNAV = "Markup is only available for images and PDFs."


# Convention "XID(k)"
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# Convention "NF(A)"
def NF(a):
    return f"Attachment {a.id} not found."


# Conventions "Payloads"
PT = {"x": 0.1, "y": 0.2}
STROKE = {"color": "#ff0000", "width": 0.5, "points": [PT]}
BARE = {**STROKE, "points": []}
TEXT = {"x": 0.1, "y": 0.1, "text": "OK", "color": "#000000", "size": 0.05}
STAMPM = {"id": None, "x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1}
SCRIB = {"color": "#f00", "width": 0.01, "points": [PT]}
SCRIB0 = {**SCRIB, "points": []}
P1 = {"1": {"strokes": [STROKE]}}
P2 = {"2": {"texts": [TEXT]}}
P12 = {"1": {"strokes": [STROKE]}, "2": {"stamps": [STAMPM]}}
EMPTY = {}
EMPTYPAGE = {"1": {"strokes": [], "texts": [], "scribbles": [], "stamps": []}}


def MP(d):
    return MarkupPayload.model_validate({"pages": d})


def D(d):
    return MP(d).model_dump()


# Conventions "Stamps"
TOKEN = "0123456789abcdef0123456789abcdef"
TOKEN31 = TOKEN[:31]
TOKEN33 = TOKEN + "0"
TOKENU = TOKEN.upper()
TOKENG = TOKEN[:31] + "g"
VEC = {
    "kind": "vector",
    "strokes": [{"color": "#000000", "width": 0.5, "points": []}],
    "viewBox": {"width": 100, "height": 50},
}
URLP = "https://res.cloudinary.com/demo-cloud/image/authenticated/"


def OWN(u):
    return f"development/profiles/{u.id}/stamp-" + TOKEN


def PROD(u):
    return f"profiles/{u.id}/stamp-" + TOKEN


def IMG(pid):
    return {"kind": "image", "public_id": pid, "url": "https://tracker.example/p.png", "width": 10, "height": 10}


# xfail markers (reason = bug id and title, docs/testing/bugs.md)
X2115 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2115: any member sees and draws marks on attachments of a private project "
    "or another member's help ticket"))
X2116 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2116: markup layers send an author's old image stamp even when it names another file"))
X2117 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2117: markup layers send a stamp picture address the browser chose"))
X2118 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2118: saving unchanged marks writes a markup_updated history entry"))
X2119 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2119: markup layers and history read the author's profile once or twice per row"))
X2120 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2120: two first saves of one user's layer at once: the second answers 500"))
X2103 = pytest.mark.xfail(strict=True, reason=(
    "BUG-2103: the workspace owner (owner_user_id) does not open another member's help ticket"))
X1435 = pytest.mark.xfail(strict=False, reason=(
    "BUG-1435: markup layers saved at one moment come back in no fixed order"))


# --------------------------------------------------------------------------- #
# Settings (every test)
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def amup_settings(monkeypatch):
    monkeypatch.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "development")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "demo-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "123456")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", "s3cret")
    return monkeypatch


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows and Given rows
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Given row "member(U, role, status="active", ws=W1)"
def member(db, S, u, role, status="active", ws=None):
    ws = ws or S.W1
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status))


# Given row "att(name)"; `deleted` = "deleted att"; `over` = the columns after "but"
def att(db, S, name, deleted=False, **over):
    fields = {
        "workspace_id": S.W1.id, "file_name": name, "mime_type": "image/png", "file_size": 100,
        "uploaded_by": S.U1.id, "upload_status": "ready", "format": "png",
    }
    if deleted:
        fields.update(is_deleted=True, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Attachment(**fields))


# Given row "link(A, type, eid)"
def link(db, S, a, etype, eid):
    return _add(db, AttachmentLink(
        workspace_id=a.workspace_id, attachment_id=a.id, entity_type=etype, entity_id=eid, linked_by=S.U1.id))


# Given row: a link filed under another workspace (cards write AttachmentLink(workspace_id=W2.id, ...))
def link_in(db, S, ws, a, etype, eid):
    return _add(db, AttachmentLink(
        workspace_id=ws.id, attachment_id=a.id, entity_type=etype, entity_id=eid, linked_by=S.U1.id))


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db, name="Ana Rahman")
    s.U2 = make_profile(db, name="Bilal Khan")
    s.UG = make_profile(db, name="Mia Khan")
    member(db, s, s.U1, "ground-team")
    member(db, s, s.U2, "owner")
    member(db, s, s.UG, "ground-team")
    s.F0 = _add(db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0"))
    s.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1"))
    s.F9 = _add(db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9"))
    s.A1 = att(db, s, "plan.png")
    link(db, s, s.A1, "scratch", 1)
    return s


# Given row "proj(name)" / "W0 proj" / "W2 proj"; `private`, `deleted` as Conventions
def proj(db, S, name, where="W1", private=False, deleted=False, **over):
    ws = getattr(S, where)
    factory = {"W0": S.F0, "W1": S.F1, "W2": S.F9}[where]
    fields = {
        "workspace_id": ws.id, "factory_id": factory.id, "name": name, "description": "Main",
        "created_by": S.U1.id, "visibility": "workspace",
    }
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Project(**fields))


def pmem(db, S, p, u):
    return _add(db, ProjectMember(workspace_id=p.workspace_id, project_id=p.id, user_id=u.id, assigned_by=S.U1.id))


def comp(db, p, name):
    return _add(db, ProjectComponent(workspace_id=p.workspace_id, project_id=p.id, name=name))


# Given row "mach(name)" / "W0 mach" / "W2 mach" / "deleted mach"
def mach(db, S, name, where="W1", deleted=False):
    ws = getattr(S, where)
    factory = {"W0": S.F0, "W1": S.F1, "W2": S.F9}[where]
    fields = {"workspace_id": ws.id, "name": name, "factory_id": factory.id}
    if deleted:
        fields["is_deleted"] = True
    return _add(db, Machine(**fields))


def item(db, S, name, **over):
    fields = {"workspace_id": S.W1.id, "name": name, "name_normalized": name.lower(), "unit": "pcs"}
    fields.update(over)
    return _add(db, Item(**fields))


def ticket(db, S, n, **over):
    fields = {
        "workspace_id": S.W1.id, "ticket_number": n, "title": "Printer jam", "description": "It jams",
        "created_by": S.U1.id,
    }
    fields.update(over)
    return _add(db, HelpTicket(**fields))


def set_owner(db, ws, u):
    ws.owner_user_id = u.id
    db.flush()


def admin(db, u):
    u.is_platform_admin = True
    db.flush()


def stamp(db, u, v):
    u.saved_stamp = v
    db.flush()


# Given row "layer(A, U, P)"; `ws` = "but workspace_id W" (PL-30, DL-14)
def layer(db, a, u, p, ws=None):
    wid = ws.id if ws is not None else a.workspace_id
    return _add(db, AttachmentMarkup(workspace_id=wid, attachment_id=a.id, user_id=u.id, payload=D(p)))


def mev(db, a, u, at):
    return _add(db, AttachmentMarkupEvent(
        workspace_id=a.workspace_id, attachment_id=a.id, user_id=u.id, event_type="markup_saved",
        description="seed", created_at=at))


def older(db, x, h):
    db.execute(
        text("UPDATE attachment_markups SET updated_at = now() - make_interval(hours => :h) WHERE id = :i"),
        {"h": h, "i": x.id},
    )
    db.expire_all()


def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def touchL(db, x):
    db.execute(text("UPDATE attachment_markups SET user_id = user_id WHERE id = :i"), {"i": x.id})
    db.expire_all()


def touchE(db, x):
    db.execute(text("UPDATE attachment_markup_events SET description = 'seed' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #

def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def NOW_DB(db):
    return db.scalar(text("SELECT now()"))


def layers_of(db, a):
    db.expire_all()
    return db.execute(
        select(AttachmentMarkup).where(AttachmentMarkup.attachment_id == a.id).order_by(AttachmentMarkup.id)
    ).scalars().all()


def events_of(db, a):
    db.expire_all()
    return db.execute(
        select(AttachmentMarkupEvent).where(AttachmentMarkupEvent.attachment_id == a.id)
        .order_by(AttachmentMarkupEvent.id)
    ).scalars().all()


def counts(db):
    """"nothing written": rows of attachment_markups and attachment_markup_events (all workspaces)."""
    return tuple(
        db.execute(select(func.count()).select_from(m)).scalar_one()
        for m in (AttachmentMarkup, AttachmentMarkupEvent)
    )


# Given step "recorder"
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


def profile_reads(stmts):
    return sum(1 for s in stmts if s.lstrip().upper().startswith("SELECT") and "FROM profiles" in s)


def markup_reads(stmts):
    return sum(1 for s in stmts if "attachment_markups" in s)


def uids(x):
    return [r.user_id for r in x]


def eids(x):
    return [r.id for r in x]


# Convention "call_uid(fn, **kw)": user_id= only when the callable has that parameter (PR-5)
def call_uid(fn, *args, user_id, **kw):
    if "user_id" in inspect.signature(fn).parameters:
        return fn(*args, user_id=user_id, **kw)
    return fn(*args, **kw)


# =========================================================================== #
# _get_ready_attachment
# =========================================================================== #

def test_amup_gr_01__ready_image_returned(db, S):
    """AMUP-GR-01 — a ready image of the caller's workspace is returned.
    Rules: _get_ready_attachment R1."""
    A2 = att(db, S, "photo.png")
    link(db, S, A2, "scratch", 2)
    att(db, S, "other.png")
    result = call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    # Then 1
    assert result.id == A2.id
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted


def test_amup_gr_02__pdf_by_format_returned(db, S):
    """AMUP-GR-02 — a ready PDF known only by its format is returned.
    Rules: _get_ready_attachment R1; _is_markupable R2."""
    A2 = att(db, S, "scan.bin", mime_type="application/octet-stream", format="PDF")
    link(db, S, A2, "scratch", 2)
    result = call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    # Then 1
    assert result.id == A2.id


def test_amup_gr_03__unknown_id_not_found(db, S):
    """AMUP-GR-03 — an unknown id is not found.
    Rules: _get_ready_attachment R2; Errors row 1."""
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=MISSING)
    assert str(exc.value) == "Attachment 999999999 not found."


def test_amup_gr_04__soft_deleted_not_found(db, S):
    """AMUP-GR-04 — a soft-deleted attachment is not found.
    Rules: _get_ready_attachment R2."""
    AD = att(db, S, "gone.png", deleted=True)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=AD.id)
    assert str(exc.value) == NF(AD)


def test_amup_gr_05__w0_attachment_not_found(db, S):
    """AMUP-GR-05 — an attachment of W0 (lower workspace id) is not found from W1.
    Rules: _get_ready_attachment R2."""
    A0 = att(db, S, "zero.png", workspace_id=S.W0.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A0.id)
    assert str(exc.value) == NF(A0)


def test_amup_gr_06__w2_attachment_not_found(db, S):
    """AMUP-GR-06 — an attachment of W2 (higher workspace id) is not found from W1.
    Rules: _get_ready_attachment R2."""
    A9 = att(db, S, "far.png", workspace_id=S.W2.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A9.id)
    assert str(exc.value) == NF(A9)


def test_amup_gr_07__pending_image_unavailable(db, S):
    """AMUP-GR-07 — a pending image is refused as unavailable.
    Rules: _get_ready_attachment R3; Errors row 2."""
    A2 = att(db, S, "wait.png", upload_status="pending")
    link(db, S, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    assert str(exc.value) == "Markup is only available for images and PDFs."


def test_amup_gr_08__failed_pdf_unavailable(db, S):
    """AMUP-GR-08 — a failed PDF is refused as unavailable.
    Rules: _get_ready_attachment R3."""
    A2 = att(db, S, "bad.pdf", mime_type="application/pdf", format="pdf", upload_status="failed")
    link(db, S, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    assert str(exc.value) == UNAV


def test_amup_gr_09__ready_csv_unavailable(db, S):
    """AMUP-GR-09 — a ready CSV is refused as unavailable.
    Rules: _get_ready_attachment R4."""
    A2 = att(db, S, "data.csv", mime_type="text/csv", format="csv")
    link(db, S, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    assert str(exc.value) == UNAV


def test_amup_gr_10__ready_docx_unavailable(db, S):
    """AMUP-GR-10 — a ready .docx is refused as unavailable.
    Rules: _get_ready_attachment R4."""
    A2 = att(
        db, S, "spec.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", format="docx",
    )
    link(db, S, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        call_uid(M._get_ready_attachment, db, user_id=S.UG.id, workspace_id=S.W1.id, attachment_id=A2.id)
    assert str(exc.value) == UNAV


@X2115
def test_amup_gr_11__private_project_hidden_from_plain_member(db, S):
    """AMUP-GR-11 — a private project's attachment is hidden from a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_12__private_project_creator_opens(db, S):
    """AMUP-GR-12 — the private project's creator opens its attachment.
    Rules: _get_ready_attachment R5 [BUG-2115], R1."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_13__project_member_opens_private(db, S):
    """AMUP-GR-13 — a project member opens the private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P, S.UG)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_14__owner_role_opens_private(db, S):
    """AMUP-GR-14 — an active workspace owner-role member opens it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_15__gtm_opens_private(db, S):
    """AMUP-GR-15 — an active ground-team-manager opens it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "ground-team-manager")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_16__workspace_owner_without_membership_opens(db, S):
    """AMUP-GR-16 — the workspace owner with no membership opens it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    U3 = make_profile(db, name="Rafi Das")
    set_owner(db, S.W1, U3)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_17__owning_w0_does_not_open(db, S):
    """AMUP-GR-17 — owning W0 does not open a W1 private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    set_owner(db, S.W0, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_18__owning_w2_does_not_open(db, S):
    """AMUP-GR-18 — owning W2 does not open a W1 private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    set_owner(db, S.W2, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_19__owner_role_only_in_w0(db, S):
    """AMUP-GR-19 — owner role only in W0 does not open it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    member(db, S, S.UG, "owner", ws=S.W0)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_20__gtm_only_in_w2(db, S):
    """AMUP-GR-20 — ground-team-manager only in W2 does not open it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    member(db, S, S.UG, "ground-team-manager", ws=S.W2)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_21__suspended_owner_role(db, S):
    """AMUP-GR-21 — a suspended owner-role member does not open it.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "owner", status="suspended")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_22__other_private_project_memberships(db, S):
    """AMUP-GR-22 — membership of other private projects (lower and higher id) does not open this one.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    PA = proj(db, S, "Alpha", private=True)
    pmem(db, S, PA, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    PB = proj(db, S, "Beta", private=True)
    pmem(db, S, PB, S.UG)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_23__creator_of_other_projects(db, S):
    """AMUP-GR-23 — having created other projects (lower and higher id) does not open this one.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    proj(db, S, "Alpha", private=True, created_by=S.UG.id)
    P = proj(db, S, "Tender 7", private=True)
    proj(db, S, "Beta", private=True, created_by=S.UG.id)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_24__private_project_without_creator(db, S):
    """AMUP-GR-24 — a private project with no creator stays closed to a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True, created_by=None)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_25__workspace_project_open(db, S):
    """AMUP-GR-25 — a workspace-visible project's attachment is open to a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115], R1."""
    P = proj(db, S, "Open Job")
    A2 = att(db, S, "open.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_26__private_component_hidden(db, S):
    """AMUP-GR-26 — a component of a private project is hidden from a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2 (component)."""
    P = proj(db, S, "Tender 7", private=True)
    C = comp(db, P, "Roof")
    A2 = att(db, S, "roof.png")
    link(db, S, A2, "project_component", C.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_27__member_opens_private_component(db, S):
    """AMUP-GR-27 — a member of the private project opens its component's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P, S.UG)
    C = comp(db, P, "Roof")
    A2 = att(db, S, "roof.png")
    link(db, S, A2, "project_component", C.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_28__deleted_project_hidden_from_creator(db, S):
    """AMUP-GR-28 — a deleted project's attachment is hidden even from its creator.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    P = proj(db, S, "Old Job", deleted=True)
    A2 = att(db, S, "old.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_29__component_of_deleted_project_hidden(db, S):
    """AMUP-GR-29 — a live component of a deleted project is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    P = proj(db, S, "Old Job", deleted=True)
    C = comp(db, P, "Roof")
    A2 = att(db, S, "roof.png")
    link(db, S, A2, "project_component", C.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_30__w0_project_link_hidden(db, S):
    """AMUP-GR-30 — a link to a W0 project is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    P0 = proj(db, S, "Zero Job", where="W0")
    A2 = att(db, S, "zero.png")
    link(db, S, A2, "project", P0.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_31__w2_project_link_hidden(db, S):
    """AMUP-GR-31 — a link to a W2 project is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    P9 = proj(db, S, "Far Job", where="W2")
    A2 = att(db, S, "far.png")
    link(db, S, A2, "project", P9.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_32__project_id_only_a_ticket(db, S):
    """AMUP-GR-32 — a project id that exists only as a W1 help ticket is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    ticket(db, S, "HT-1", id=XID(1))
    A2 = att(db, S, "x.png")
    link(db, S, A2, "project", XID(1))
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_33__ticket_id_only_a_project(db, S):
    """AMUP-GR-33 — a ticket id that exists only as a W1 project is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    proj(db, S, "Open Job", id=XID(2))
    A2 = att(db, S, "x.png")
    link(db, S, A2, "support_ticket", XID(2))
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_34__unknown_purchase_order_hidden(db, S):
    """AMUP-GR-34 — an unknown purchase order id is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    A2 = att(db, S, "po.png")
    link(db, S, A2, "purchase_order", MISSING)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_35__other_members_ticket_hidden(db, S):
    """AMUP-GR-35 — another member's help ticket is hidden from a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2 (ticket)."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_36__ticket_creator_opens(db, S):
    """AMUP-GR-36 — the ticket's creator opens its attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_37__owner_role_opens_others_ticket(db, S):
    """AMUP-GR-37 — an active owner-role member opens another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_38__platform_admin_opens_others_ticket(db, S):
    """AMUP-GR-38 — a platform admin opens another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    admin(db, S.UG)
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_39__creator_of_other_tickets(db, S):
    """AMUP-GR-39 — creating other tickets (lower and higher id) does not open this one.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    ticket(db, S, "HT-1", created_by=S.UG.id)
    T = ticket(db, S, "HT-2")
    ticket(db, S, "HT-3", created_by=S.UG.id)
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_40__capital_owner_role_and_no_creator(db, S):
    """AMUP-GR-40 — a ticket with no creator is hidden from a member whose role is "Owner" (capital O).
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "Owner")
    T = ticket(db, S, "HT-1", created_by=None)
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_41__hidden_link_first(db, S):
    """AMUP-GR-41 — one hidden link among two hides the attachment (hidden link first).
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-3 "any link"."""
    PP = proj(db, S, "Tender 7", private=True)
    PO = proj(db, S, "Open Job")
    A2 = att(db, S, "both.png")
    link(db, S, A2, "project", PP.id)
    link(db, S, A2, "project", PO.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_42__hidden_link_second(db, S):
    """AMUP-GR-42 — one hidden link among two hides the attachment (hidden link second).
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-3 "any link"."""
    PP = proj(db, S, "Tender 7", private=True)
    PO = proj(db, S, "Open Job")
    A2 = att(db, S, "both.png")
    link(db, S, A2, "project", PO.id)
    link(db, S, A2, "project", PP.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_43__hidden_and_pending_is_not_found(db, S):
    """AMUP-GR-43 — a hidden attachment that is also pending answers not found, not unavailable.
    Rules: _get_ready_attachment R5 [BUG-2115] (checked before R3)."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "wait.png", upload_status="pending")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert type(exc.value) is AttachmentNotFoundError
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_44__hidden_csv_is_not_found(db, S):
    """AMUP-GR-44 — a hidden CSV answers not found, not unavailable.
    Rules: _get_ready_attachment R5 [BUG-2115] (checked before R4)."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "data.csv", mime_type="text/csv", format="csv")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert type(exc.value) is AttachmentNotFoundError
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_45__gtm_opens_others_ticket(db, S):
    """AMUP-GR-45 — an active ground-team-manager opens another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "ground-team-manager")
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_46__live_machine_open(db, S):
    """AMUP-GR-46 — a live W1 machine's attachment is open to a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115], R1; PR-2 (workspace-wide type)."""
    MC = mach(db, S, "Lathe 1")
    A2 = att(db, S, "lathe.png")
    link(db, S, A2, "machine", MC.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_47__deleted_machine_hidden(db, S):
    """AMUP-GR-47 — a deleted machine's attachment is hidden even from an owner-role member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    MC = mach(db, S, "Lathe 1", deleted=True)
    A2 = att(db, S, "lathe.png")
    link(db, S, A2, "machine", MC.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_48__w0_machine_hidden(db, S):
    """AMUP-GR-48 — a link to a W0 machine is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    M0 = mach(db, S, "Zero Lathe", where="W0")
    A2 = att(db, S, "lathe.png")
    link(db, S, A2, "machine", M0.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_49__w2_machine_hidden(db, S):
    """AMUP-GR-49 — a link to a W2 machine is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    M9 = mach(db, S, "Far Lathe", where="W2")
    A2 = att(db, S, "lathe.png")
    link(db, S, A2, "machine", M9.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_50__machine_id_only_an_item(db, S):
    """AMUP-GR-50 — a machine id that exists only as a W1 item is hidden.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1."""
    item(db, S, "Bolt", id=XID(5))
    A2 = att(db, S, "bolt.png")
    link(db, S, A2, "machine", XID(5))
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_51__live_item_open(db, S):
    """AMUP-GR-51 — a live W1 item's attachment is open to a plain member.
    Rules: _get_ready_attachment R5 [BUG-2115], R1; PR-2 (workspace-wide type)."""
    IT = item(db, S, "Bolt")
    A2 = att(db, S, "bolt.png")
    link(db, S, A2, "item", IT.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_52__suspended_gtm_private_project(db, S):
    """AMUP-GR-52 — a suspended ground-team-manager does not open a private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "ground-team-manager", status="suspended")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_53__inactive_owner_private_project(db, S):
    """AMUP-GR-53 — a removed (inactive) owner-role member does not open a private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "owner", status="inactive")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_54__owner_role_only_in_w2_private_project(db, S):
    """AMUP-GR-54 — owner role only in W2 does not open a private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)."""
    member(db, S, S.UG, "owner", ws=S.W2)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_55__suspended_owner_others_ticket(db, S):
    """AMUP-GR-55 — a suspended owner-role member does not open another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "owner", status="suspended")
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_56__inactive_gtm_others_ticket(db, S):
    """AMUP-GR-56 — a removed (inactive) ground-team-manager does not open another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "ground-team-manager", status="inactive")
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_57__owner_role_only_in_w0_ticket(db, S):
    """AMUP-GR-57 — owner role only in W0 does not open a W1 ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)."""
    member(db, S, S.UG, "owner", ws=S.W0)
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_58__gtm_only_in_w2_ticket(db, S):
    """AMUP-GR-58 — ground-team-manager only in W2 does not open a W1 ticket.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)."""
    member(db, S, S.UG, "ground-team-manager", ws=S.W2)
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_59__only_link_filed_under_w2(db, S):
    """AMUP-GR-59 — an attachment whose only link is filed under W2 answers not found.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-3 (only own-workspace links count)."""
    A2 = att(db, S, "stray.png")
    link_in(db, S, S.W2, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_60__no_link_at_all(db, S):
    """AMUP-GR-60 — an attachment with no link at all answers not found.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-3 (no own-workspace link)."""
    A2 = att(db, S, "lonely.png")
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_61__w2_filed_link_ignored(db, S):
    """AMUP-GR-61 — a link filed under W2 to a private W2 project is ignored; the W1 link decides.
    Rules: _get_ready_attachment R5 [BUG-2115], R1; PR-3 (other-workspace links ignored)."""
    P9 = proj(db, S, "Far Job", where="W2", private=True)
    A2 = att(db, S, "mixed.png")
    link(db, S, A2, "scratch", 2)
    link_in(db, S, S.W2, A2, "project", P9.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_62__non_member_opens_workspace_project(db, S):
    """AMUP-GR-62 — a caller with no W1 membership opens a workspace-visible project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115], R1; PR-2 (no membership check of its own)."""
    U3 = make_profile(db, name="Rafi Das")
    P = proj(db, S, "Open Job")
    A2 = att(db, S, "open.png")
    link(db, S, A2, "project", P.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    # Then 1
    assert result.id == A2.id


@X2115
def test_amup_gr_63__non_member_judged_on_private_project(db, S):
    """AMUP-GR-63 — a caller with no W1 membership is still judged on a private project.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2 (private records judged in full)."""
    U3 = make_profile(db, name="Rafi Das")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_64__platform_admin_refused_private_project(db, S):
    """AMUP-GR-64 — a platform admin with a plain role does not open a private project's attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2 (platform admin counts for help tickets only)."""
    admin(db, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_65__platform_admin_refused_private_component(db, S):
    """AMUP-GR-65 — a platform admin with a plain role does not open a private project's component attachment.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-2 (component → its project's rule)."""
    admin(db, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    C = comp(db, P, "Frame")
    A2 = att(db, S, "frame.png")
    link(db, S, A2, "project_component", C.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_66__w1_link_to_w2_ticket_hidden(db, S):
    """AMUP-GR-66 — a W1-filed link to a W2 help ticket is hidden, even from a W1 owner-role member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    T9 = ticket(db, S, "HT-9", workspace_id=S.W2.id)
    A2 = att(db, S, "far.png")
    link(db, S, A2, "support_ticket", T9.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_gr_67__w1_link_to_w0_ticket_hidden(db, S):
    """AMUP-GR-67 — a W1-filed link to a W0 help ticket is hidden, even from a W1 owner-role member.
    Rules: _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16."""
    T0w = ticket(db, S, "HT-0", workspace_id=S.W0.id)
    A2 = att(db, S, "zero.png")
    link(db, S, A2, "support_ticket", T0w.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2103
def test_amup_gr_68__workspace_owner_opens_others_ticket(db, S):
    """AMUP-GR-68 — the workspace owner with a plain role opens another member's ticket.
    Rules: _get_ready_attachment R5 [BUG-2103, BUG-2115]; PR-2 (workspace owner opens every ticket)."""
    set_owner(db, S.W1, S.UG)
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    result = M._get_ready_attachment(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    # Then 1
    assert result.id == A2.id


# =========================================================================== #
# _is_markupable (pure: Attachment built, never added)
# =========================================================================== #

def test_amup_im_01__application_pdf_markable():
    """AMUP-IM-01 — mime application/pdf is markable whatever the format.
    Rules: _is_markupable R1."""
    a = Attachment(mime_type="application/pdf", format="bin")
    result = AttachmentMarkupManager._is_markupable(a)
    # Then 1
    assert result is True


def test_amup_im_02__format_pdf_any_case_markable():
    """AMUP-IM-02 — format "PDF" or "pdf" is markable with a non-image mime.
    Rules: _is_markupable R2."""
    a1 = Attachment(mime_type="text/plain", format="PDF")
    a2 = Attachment(mime_type="text/plain", format="pdf")
    result = [AttachmentMarkupManager._is_markupable(a) for a in (a1, a2)]
    # Then 1
    assert result == [True, True]


def test_amup_im_03__near_pdf_formats_not_pdf():
    """AMUP-IM-03 — format "pd", " pdf" and "pdfx" are not PDF.
    Rules: _is_markupable R2."""
    xs = [Attachment(mime_type="text/plain", format=f) for f in ("pd", " pdf", "pdfx")]
    result = [AttachmentMarkupManager._is_markupable(a) for a in xs]
    # Then 1
    assert result == [False, False, False]


def test_amup_im_04__near_pdf_mimes_not_pdf():
    """AMUP-IM-04 — mime "application/PDF", "application/pd" and " application/pdf" are not PDF.
    Rules: _is_markupable R1."""
    xs = [Attachment(mime_type=m, format="bin") for m in ("application/PDF", "application/pd", " application/pdf")]
    result = [AttachmentMarkupManager._is_markupable(a) for a in xs]
    # Then 1
    assert result == [False, False, False]


def test_amup_im_05__image_mimes_markable():
    """AMUP-IM-05 — image/png and image/heic are markable.
    Rules: _is_markupable R3."""
    xs = [Attachment(mime_type=m, format="bin") for m in ("image/png", "image/heic")]
    result = [AttachmentMarkupManager._is_markupable(a) for a in xs]
    # Then 1
    assert result == [True, True]


def test_amup_im_06__near_image_mimes_not_markable():
    """AMUP-IM-06 — "Image/png", " image/png", "x-image/png" and "image" are not markable.
    Rules: _is_markupable R3."""
    xs = [Attachment(mime_type=m, format="bin") for m in ("Image/png", " image/png", "x-image/png", "image")]
    result = [AttachmentMarkupManager._is_markupable(a) for a in xs]
    # Then 1
    assert result == [False, False, False, False]


def test_amup_im_07__csv_not_markable():
    """AMUP-IM-07 — text/csv is not markable.
    Rules: _is_markupable R3."""
    a = Attachment(mime_type="text/csv", format="csv")
    result = AttachmentMarkupManager._is_markupable(a)
    # Then 1
    assert result is False


def test_amup_im_08__none_and_none_not_markable():
    """AMUP-IM-08 — mime None and format None is not markable, without error.
    Rules: _is_markupable R4."""
    a = Attachment(mime_type=None, format=None)
    result = AttachmentMarkupManager._is_markupable(a)
    # Then 1
    assert result is False


def test_amup_im_09__none_mime_pdf_format_markable():
    """AMUP-IM-09 — mime None with format "pdf" is markable.
    Rules: _is_markupable R2, R4."""
    a = Attachment(mime_type=None, format="pdf")
    result = AttachmentMarkupManager._is_markupable(a)
    # Then 1
    assert result is True


def test_amup_im_10__none_format_jpeg_markable():
    """AMUP-IM-10 — format None with mime image/jpeg is markable.
    Rules: _is_markupable R3, R4."""
    a = Attachment(mime_type="image/jpeg", format=None)
    result = AttachmentMarkupManager._is_markupable(a)
    # Then 1
    assert result is True


# =========================================================================== #
# _resolve_user_name
# =========================================================================== #

def test_amup_un_01__existing_profile_name(db, S):
    """AMUP-UN-01 — an existing profile's name, between lower and higher profile ids.
    Rules: _resolve_user_name R1."""
    result = M._resolve_user_name(db, S.U2.id)
    # Then 1
    assert result == "Bilal Khan"


def test_amup_un_02__profile_without_membership(db, S):
    """AMUP-UN-02 — a profile with no membership anywhere still gives its name.
    Rules: _resolve_user_name R1 (D8)."""
    U3 = make_profile(db, name="Lena Roy")
    result = M._resolve_user_name(db, U3.id)
    # Then 1
    assert result == "Lena Roy"


def test_amup_un_03__unknown_id_placeholder(db, S):
    """AMUP-UN-03 — an unknown id gives "User #<id>".
    Rules: _resolve_user_name R2."""
    result = M._resolve_user_name(db, MISSING)
    # Then 1
    assert result == "User #999999999"


# =========================================================================== #
# _resolve_saved_stamp
# =========================================================================== #

def test_amup_ss_01__no_profile_none(db, S):
    """AMUP-SS-01 — no profile gives None.
    Rules: _resolve_saved_stamp R2."""
    result = M._resolve_saved_stamp(db, MISSING)
    # Then 1
    assert result is None


def test_amup_ss_02__stamp_none_gives_none(db, S):
    """AMUP-SS-02 — saved_stamp None gives None.
    Rules: _resolve_saved_stamp R2."""
    stamp(db, S.U1, None)
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_03__empty_object_gives_none(db, S):
    """AMUP-SS-03 — saved_stamp {} gives None.
    Rules: _resolve_saved_stamp R2."""
    stamp(db, S.U1, {})
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_04__list_gives_none(db, S):
    """AMUP-SS-04 — a stored list gives None.
    Rules: _resolve_saved_stamp R3."""
    stamp(db, S.U1, [VEC])
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_05__string_gives_none(db, S):
    """AMUP-SS-05 — a stored string gives None.
    Rules: _resolve_saved_stamp R3."""
    stamp(db, S.U1, "image")
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_06__number_gives_none(db, S):
    """AMUP-SS-06 — a stored number gives None.
    Rules: _resolve_saved_stamp R3."""
    stamp(db, S.U1, 7)
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_07__vector_as_stored(db, S):
    """AMUP-SS-07 — a vector stamp is returned as stored.
    Rules: _resolve_saved_stamp R4."""
    stamp(db, S.U1, VEC)
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result == VEC


def test_amup_ss_08__own_stamp_not_neighbours(db, S):
    """AMUP-SS-08 — the author's own stamp is read, not a neighbour's (lower and higher ids).
    Rules: _resolve_saved_stamp R1, R4."""
    stamp(db, S.U1, {"kind": "vector", "strokes": [], "viewBox": {"width": 1, "height": 1}})
    stamp(db, S.U2, VEC)
    stamp(db, S.UG, {"kind": "vector", "strokes": [], "viewBox": {"width": 9, "height": 9}})
    result = M._resolve_saved_stamp(db, S.U2.id)
    # Then 1
    assert result == VEC


def test_amup_ss_09__no_kind_as_stored(db, S):
    """AMUP-SS-09 — a stamp with no kind is returned as stored.
    Rules: _resolve_saved_stamp R5."""
    stamp(db, S.U1, {"shape": "x"})
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result == {"shape": "x"}


def test_amup_ss_33__unknown_kind_as_stored(db, S):
    """AMUP-SS-33 — a stamp with an unknown kind is returned as stored.
    Rules: _resolve_saved_stamp R5."""
    stamp(db, S.U1, {"kind": "text", "text": "OK"})
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result == {"kind": "text", "text": "OK"}


def test_amup_ss_10__own_minted_image_keeps_fields(db, S):
    """AMUP-SS-10 — the author's own minted image stamp keeps kind, public_id, width and height.
    Rules: _resolve_saved_stamp R4a (accepted side), R4b (fields kept)."""
    stamp(db, S.U1, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["kind"] == "image"
    assert result["public_id"] == OWN(S.U1)
    assert result["width"] == 10
    assert result["height"] == 10


def test_amup_ss_11__production_bare_own_form(db, S, amup_settings):
    """AMUP-SS-11 — in production the bare own form keeps its fields.
    Rules: _resolve_saved_stamp R4a (production)."""
    amup_settings.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "production")
    stamp(db, S.U1, IMG(PROD(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["kind"] == "image"
    assert result["public_id"] == PROD(S.U1)
    assert result["width"] == 10
    assert result["height"] == 10


@X2117
def test_amup_ss_12__server_built_url(db, S):
    """AMUP-SS-12 — the server builds the url of an own stamp; the stored url never appears.
    Rules: _resolve_saved_stamp R4b [BUG-2117]."""
    stamp(db, S.U1, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["public_id"] == OWN(S.U1)
    # Then 2
    assert result["url"].startswith(URLP)
    # Then 3
    assert OWN(S.U1) in result["url"]
    # Then 4
    assert "tracker.example" not in result["url"]


@X2117
def test_amup_ss_13__url_follows_cloud_name(db, S, amup_settings):
    """AMUP-SS-13 — the url follows the configured cloud name.
    Rules: _resolve_saved_stamp R4b [BUG-2117]."""
    amup_settings.setattr(settings, "CLOUDINARY_CLOUD_NAME", "acme-cloud")
    stamp(db, S.U1, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["url"].startswith("https://res.cloudinary.com/acme-cloud/image/authenticated/")


@X2117
def test_amup_ss_14__production_url_from_bare_id(db, S, amup_settings):
    """AMUP-SS-14 — in production the url is built from the bare own id.
    Rules: _resolve_saved_stamp R4b [BUG-2117]."""
    amup_settings.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "production")
    stamp(db, S.U1, IMG(PROD(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["url"].startswith(URLP)
    # Then 2
    assert PROD(S.U1) in result["url"]


@X2116
def test_amup_ss_15__higher_users_id_on_lower_author(db, S):
    """AMUP-SS-15 — a higher-id user's stamp id on a lower-id author is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(OWN(S.U2)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_16__lower_users_id_on_higher_author(db, S):
    """AMUP-SS-16 — a lower-id user's stamp id on a higher-id author is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.UG, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.UG.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_17__attachment_public_id_dropped(db, S):
    """AMUP-SS-17 — an attachment's public id is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/ws-{S.W1.id}/" + TOKEN))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_18__bare_prefix_dropped(db, S):
    """AMUP-SS-18 — the bare prefix is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/profiles/{S.U1.id}/stamp-"))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_19__token_31_dropped(db, S):
    """AMUP-SS-19 — a 31-character token is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/profiles/{S.U1.id}/stamp-" + TOKEN31))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_20__token_33_dropped(db, S):
    """AMUP-SS-20 — a 33-character token is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/profiles/{S.U1.id}/stamp-" + TOKEN33))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_21__upper_case_token_dropped(db, S):
    """AMUP-SS-21 — an upper-case token is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/profiles/{S.U1.id}/stamp-" + TOKENU))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_22__non_hex_token_dropped(db, S):
    """AMUP-SS-22 — a token with a non-hex letter is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"development/profiles/{S.U1.id}/stamp-" + TOKENG))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_23__suffix_after_token_dropped(db, S):
    """AMUP-SS-23 — anything after a valid token (".png") is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(OWN(S.U1) + ".png"))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_24__trailing_newline_dropped(db, S):
    """AMUP-SS-24 — a trailing newline after a valid token is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(OWN(S.U1) + "\n"))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_25__production_form_in_development_dropped(db, S):
    """AMUP-SS-25 — the production form is dropped in development.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(PROD(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_26__development_form_in_production_dropped(db, S, amup_settings):
    """AMUP-SS-26 — the development form is dropped in production.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    amup_settings.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "production")
    stamp(db, S.U1, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


def test_amup_ss_27__staging_fallback_own_form_kept(db, S, amup_settings):
    """AMUP-SS-27 — with the upload environment empty, an own "staging" stamp keeps its fields.
    Rules: _resolve_saved_stamp R4a (accepted side, ENVIRONMENT fallback)."""
    amup_settings.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "")
    amup_settings.setattr(settings, "ENVIRONMENT", "staging")
    stamp(db, S.U1, IMG(f"staging/profiles/{S.U1.id}/stamp-" + TOKEN))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result["public_id"] == f"staging/profiles/{S.U1.id}/stamp-" + TOKEN
    assert result["width"] == 10


@X2116
def test_amup_ss_32__staging_fallback_development_form_dropped(db, S, amup_settings):
    """AMUP-SS-32 — with the upload environment empty and ENVIRONMENT "staging", the development form is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    amup_settings.setattr(settings, "CLOUDINARY_UPLOAD_ENV", "")
    amup_settings.setattr(settings, "ENVIRONMENT", "staging")
    stamp(db, S.U1, IMG(OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_28__capitalised_env_prefix_dropped(db, S):
    """AMUP-SS-28 — a capitalised environment prefix is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(f"Development/profiles/{S.U1.id}/stamp-" + TOKEN))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_29__leading_space_dropped(db, S):
    """AMUP-SS-29 — a leading space makes the id foreign.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG(" " + OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_30__image_without_public_id_dropped(db, S):
    """AMUP-SS-30 — an image stamp without public_id is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, {"kind": "image", "url": "https://tracker.example/p.png", "width": 10, "height": 10})
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


@X2116
def test_amup_ss_31__own_prefix_in_middle_dropped(db, S):
    """AMUP-SS-31 — the own prefix in the middle of the id is dropped.
    Rules: _resolve_saved_stamp R4a [BUG-2116]."""
    stamp(db, S.U1, IMG("x/" + OWN(S.U1)))
    result = M._resolve_saved_stamp(db, S.U1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# _summarize_payload (pure)
# =========================================================================== #

def test_amup_sp_01__one_page_one_stroke():
    """AMUP-SP-01 — one page with one stroke.
    Rules: _summarize_payload R1, R2, R4."""
    result = AttachmentMarkupManager._summarize_payload(MP({"3": {"strokes": [STROKE]}}))
    # Then 1
    assert result == ({"pages": [3]}, "Updated marks on page 3")


def test_amup_sp_02__bare_stroke_counts_empty_page_not():
    """AMUP-SP-02 — a stroke with no points counts; an all-empty page does not.
    Rules: _summarize_payload R1 (D9)."""
    result = AttachmentMarkupManager._summarize_payload(
        MP({"1": {"strokes": [BARE]}, "2": {"strokes": [], "texts": [], "scribbles": [], "stamps": []}})
    )
    # Then 1
    assert result == ({"pages": [1]}, "Updated marks on page 1")


def test_amup_sp_03__text_page_and_stamp_page_count():
    """AMUP-SP-03 — a page with only a text, and one with only a stamp, both count.
    Rules: _summarize_payload R1, R4."""
    result = AttachmentMarkupManager._summarize_payload(MP({"4": {"texts": [TEXT]}, "5": {"stamps": [STAMPM]}}))
    # Then 1
    assert result == ({"pages": [4, 5]}, "Updated marks on pages 4, 5")


def test_amup_sp_04__int_keys_become_integers():
    """AMUP-SP-04 — keys accepted by int() become integers.
    Rules: _summarize_payload R2, R3."""
    result = AttachmentMarkupManager._summarize_payload(
        MP({k: {"strokes": [STROKE]} for k in ("03", " 2", "-1", "1_0")})
    )
    # Then 1
    assert result[0] == {"pages": [-1, 2, 3, 10]}


def test_amup_sp_05__non_int_keys_stay_strings():
    """AMUP-SP-05 — "cover" and "1.5" stay strings.
    Rules: _summarize_payload R2."""
    result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("cover", "1.5")}))
    # Then 1
    assert result == ({"pages": ["1.5", "cover"]}, "Updated marks on pages 1.5, cover")


def test_amup_sp_06__integers_first_then_strings():
    """AMUP-SP-06 — integers first numerically, then strings.
    Rules: _summarize_payload R3."""
    result = AttachmentMarkupManager._summarize_payload(
        MP({k: {"strokes": [STROKE]} for k in ("b", "10", "2", "a")})
    )
    # Then 1
    assert result[0] == {"pages": [2, 10, "a", "b"]}


def test_amup_sp_07__same_integer_twice():
    """AMUP-SP-07 — "1" and "01" both appear.
    Rules: _summarize_payload R3."""
    result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("01", "1")}))
    # Then 1
    assert result == ({"pages": [1, 1]}, "Updated marks on pages 1, 1")


def test_amup_sp_08__several_pages_in_sort_order():
    """AMUP-SP-08 — several pages are named in sort order.
    Rules: _summarize_payload R4."""
    result = AttachmentMarkupManager._summarize_payload(
        MP({k: {"strokes": [STROKE]} for k in ("cover", "3", "1")})
    )
    # Then 1
    assert result == ({"pages": [1, 3, "cover"]}, "Updated marks on pages 1, 3, cover")


def test_amup_sp_09__no_pages():
    """AMUP-SP-09 — no pages gives "Updated marks".
    Rules: _summarize_payload R5."""
    result = AttachmentMarkupManager._summarize_payload(MP(EMPTY))
    # Then 1
    assert result == ({"pages": []}, "Updated marks")


def test_amup_sp_10__only_empty_pages():
    """AMUP-SP-10 — only all-empty pages gives "Updated marks".
    Rules: _summarize_payload R5, R1."""
    result = AttachmentMarkupManager._summarize_payload(MP(EMPTYPAGE))
    # Then 1
    assert result == ({"pages": []}, "Updated marks")


def test_amup_sp_11__scribble_pages_count():
    """AMUP-SP-11 — a page with only a scribble counts, also one with no points.
    Rules: _summarize_payload R1, R4."""
    result = AttachmentMarkupManager._summarize_payload(
        MP({"1": {"scribbles": [SCRIB]}, "2": {"scribbles": [SCRIB0]}})
    )
    # Then 1
    assert result == ({"pages": [1, 2]}, "Updated marks on pages 1, 2")


# =========================================================================== #
# _log_markup_event
# =========================================================================== #

def test_amup_le_01__one_row_with_given_values(db, S):
    """AMUP-LE-01 — one row with exactly the given values.
    Rules: _log_markup_event R1."""
    M._log_markup_event(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, event_type="markup_saved",
        description="Saved marks on page 1", session_id="tab-1", metadata_json={"pages": [1]},
    )
    # Then 1
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    # Then 2
    e = reread(db, AttachmentMarkupEvent, evs[0].id)
    assert e.workspace_id == S.W1.id
    assert e.attachment_id == S.A1.id
    assert e.user_id == S.U2.id
    assert e.event_type == "markup_saved"
    assert e.description == "Saved marks on page 1"
    assert e.session_id == "tab-1"
    assert e.metadata_json == {"pages": [1]}
    assert e.created_at is not None


def test_amup_le_02__flushed_not_committed(db, S):
    """AMUP-LE-02 — the event is flushed, not committed.
    Rules: _log_markup_event R1 (no commit)."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M._log_markup_event(
            db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, event_type="markup_cleared",
            description="Cleared marks",
        )
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(events_of(db, S.A1)) == 0


# =========================================================================== #
# _to_layer_response
# =========================================================================== #

def test_amup_tl_01__own_layer_maps_every_field(db, S):
    """AMUP-TL-01 — the caller's own layer maps every field.
    Rules: _to_layer_response R1."""
    stamp(db, S.U1, VEC)
    L = layer(db, S.A1, S.U1, P1)
    result = M._to_layer_response(db, row=L, current_user_id=S.U1.id)
    # Then 1
    assert result.user_id == S.U1.id
    assert result.user_name == "Ana Rahman"
    assert result.is_mine is True
    # Then 2
    db.refresh(L)
    assert result.updated_at == L.updated_at
    # Then 3
    assert result.payload == MP(P1)
    # Then 4
    assert result.saved_stamp == VEC


def test_amup_tl_02__other_users_layer_not_mine(db, S):
    """AMUP-TL-02 — another user's layer is not mine.
    Rules: _to_layer_response R1."""
    L = layer(db, S.A1, S.U2, P2)
    result = M._to_layer_response(db, row=L, current_user_id=S.U1.id)
    # Then 1
    assert result.user_id == S.U2.id
    assert result.user_name == "Bilal Khan"
    assert result.is_mine is False
    assert result.saved_stamp is None


def test_amup_tl_03__json_null_payload_raises(db, S):
    """AMUP-TL-03 — a stored JSON null payload raises ValidationError.
    Rules: _to_layer_response R2."""
    L = _add(db, AttachmentMarkup(workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=None))
    # Then 1
    with pytest.raises(ValidationError):
        M._to_layer_response(db, row=L, current_user_id=S.U1.id)


# =========================================================================== #
# _to_event_response
# =========================================================================== #

def test_amup_te_01__event_maps_every_field(db, S):
    """AMUP-TE-01 — an event maps every stored field; mine.
    Rules: _to_event_response R1."""
    E = _add(db, AttachmentMarkupEvent(
        workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, event_type="markup_updated",
        description="Updated marks on page 2", session_id="tab-9", metadata_json={"pages": [2]}, created_at=T1,
    ))
    result = M._to_event_response(db, row=E, current_user_id=S.U2.id)
    # Then 1
    assert result.id == E.id
    assert result.user_id == S.U2.id
    assert result.user_name == "Bilal Khan"
    assert result.is_mine is True
    # Then 2
    assert result.session_id == "tab-9"
    assert result.event_type == "markup_updated"
    assert result.description == "Updated marks on page 2"
    # Then 3
    assert result.metadata_json == {"pages": [2]}
    assert result.created_at == T1


def test_amup_te_02__other_users_event_not_mine(db, S):
    """AMUP-TE-02 — another user's event is not mine.
    Rules: _to_event_response R1."""
    E = mev(db, S.A1, S.UG, T1)
    result = M._to_event_response(db, row=E, current_user_id=S.U1.id)
    # Then 1
    assert result.user_name == "Mia Khan"
    assert result.is_mine is False


# =========================================================================== #
# list_layers
# =========================================================================== #

def test_amup_ll_01__every_author_only_callers_mine(db, S):
    """AMUP-LL-01 — every author's layer, only the caller's is mine.
    Rules: list_layers R2; D8."""
    U3 = make_profile(db, name="Lena Roy")
    layer(db, S.A1, S.U2, P1)
    layer(db, S.A1, U3, P2)
    layer(db, S.A1, S.U1, P12)
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert sorted(uids(result)) == sorted([S.U1.id, S.U2.id, U3.id])
    # Then 2
    assert {r.user_id: r.is_mine for r in result} == {S.U1.id: True, S.U2.id: False, U3.id: False}
    # Then 3
    assert {r.user_id: r.user_name for r in result}[U3.id] == "Lena Roy"


def test_amup_ll_02__other_attachments_and_workspaces_not_listed(db, S):
    """AMUP-LL-02 — layers of other attachments (lower and higher id) and other workspaces are not listed.
    Rules: list_layers R2."""
    AL = att(db, S, "low.png")
    A2 = att(db, S, "mid.png")
    link(db, S, A2, "scratch", 2)
    AH = att(db, S, "high.png")
    layer(db, AL, S.U1, P1)
    layer(db, A2, S.U2, P1)
    layer(db, AH, S.UG, P1)
    _add(db, AttachmentMarkup(workspace_id=S.W0.id, attachment_id=A2.id, user_id=S.U1.id, payload=D(P1)))
    _add(db, AttachmentMarkup(workspace_id=S.W2.id, attachment_id=A2.id, user_id=S.UG.id, payload=D(P1)))
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U1.id)
    # Then 1
    assert uids(result) == [S.U2.id]


def test_amup_ll_03__no_layers_empty_list(db, S):
    """AMUP-LL-03 — no layers gives [].
    Rules: list_layers R3."""
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert result == []


def test_amup_ll_04__oldest_updated_first(db, S):
    """AMUP-LL-04 — layers come oldest updated first.
    Rules: list_layers R3 (DAO R4, distinct times)."""
    LA = layer(db, S.A1, S.U2, P1)
    LB = layer(db, S.A1, S.UG, P1)
    layer(db, S.A1, S.U1, P1)
    older(db, LA, 1)
    older(db, LB, 2)
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert uids(result) == [S.UG.id, S.U2.id, S.U1.id]


@X1435
def test_amup_ll_05__ties_in_id_order_after_update(db, S):
    """AMUP-LL-05 — layers with one time come in id order, also after an update.
    Rules: list_layers R3 [BUG-1435]."""
    seqscan(db)
    LA = layer(db, S.A1, S.UG, P1)
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.U2, P1)
    touchL(db, LA)
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert uids(result) == [S.UG.id, S.U1.id, S.U2.id]


def test_amup_ll_06__unknown_attachment_reads_no_layer(db, S):
    """AMUP-LL-06 — an unknown attachment raises not found and no layer is read.
    Rules: list_layers R1."""
    layer(db, S.A1, S.U1, P1)
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=MISSING, current_user_id=S.U1.id)
    stop()
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 2
    assert markup_reads(stmts) == 0


def test_amup_ll_07__pending_attachment_reads_no_layer(db, S):
    """AMUP-LL-07 — a pending attachment raises unavailable and no layer is read.
    Rules: list_layers R1."""
    A2 = att(db, S, "wait.png", upload_status="pending")
    link(db, S, A2, "scratch", 2)
    layer(db, A2, S.U1, P1)
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U1.id)
    stop()
    assert str(exc.value) == UNAV
    # Then 2
    assert markup_reads(stmts) == 0


@X2115
def test_amup_ll_08__private_project_layers_hidden(db, S):
    """AMUP-LL-08 — layers on a private project's attachment are hidden from a plain member.
    Rules: list_layers R1a [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    layer(db, A2, S.U1, P1)
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.UG.id)
    stop()
    assert str(exc.value) == NF(A2)
    # Then 2
    assert markup_reads(stmts) == 0


@X2115
def test_amup_ll_09__others_ticket_layers_hidden(db, S):
    """AMUP-LL-09 — layers on another member's ticket attachment are hidden.
    Rules: list_layers R1a [BUG-2115]."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    layer(db, A2, S.U1, P1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_ll_10__w2_project_layers_hidden(db, S):
    """AMUP-LL-10 — layers on a W2 project's attachment are hidden.
    Rules: list_layers R1a [BUG-2115]."""
    P9 = proj(db, S, "Far Job", where="W2")
    A2 = att(db, S, "far.png")
    link(db, S, A2, "project", P9.id)
    layer(db, A2, S.U1, P1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


def test_amup_ll_11__project_member_lists_private_layers(db, S):
    """AMUP-LL-11 — a project member lists the private project's layers.
    Rules: list_layers R1a (granted side of BUG-2115), R2."""
    P = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P, S.UG)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    layer(db, A2, S.U1, P1)
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.UG.id)
    # Then 1
    assert uids(result) == [S.U1.id]


@X2119
def test_amup_ll_12__authors_read_together(db, S):
    """AMUP-LL-12 — authors' profiles are read together.
    Rules: list_layers R4 [BUG-2119]."""
    U3 = make_profile(db, name="Lena Roy")
    U4 = make_profile(db, name="Omar Ali")
    U5 = make_profile(db, name="Nila Sen")
    for u in (S.U1, S.U2, U3, U4, U5):
        layer(db, S.A1, u, P1)
    stmts, stop = recorder(db)
    result = M.list_layers(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    stop()
    # Then 1
    assert sorted(r.user_name for r in result) == ["Ana Rahman", "Bilal Khan", "Lena Roy", "Nila Sen", "Omar Ali"]
    # Then 2
    assert profile_reads(stmts) <= 2


@X2115
def test_amup_ll_13__only_link_under_w2_layers_hidden(db, S):
    """AMUP-LL-13 — layers of an attachment whose only link is filed under W2 are hidden.
    Rules: list_layers R1a [BUG-2115]; PR-3 (only own-workspace links count)."""
    A2 = att(db, S, "stray.png")
    link_in(db, S, S.W2, A2, "scratch", 2)
    layer(db, A2, S.U1, P1)
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U2.id)
    stop()
    assert str(exc.value) == NF(A2)
    # Then 2
    assert markup_reads(stmts) == 0


@X2115
def test_amup_ll_14__platform_admin_no_layers_private_project(db, S):
    """AMUP-LL-14 — a platform admin with a plain role sees no layers of a private project's attachment.
    Rules: list_layers R1a [BUG-2115]; PR-2."""
    admin(db, S.UG)
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    layer(db, A2, S.U1, P1)
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_layers(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.UG.id)
    stop()
    assert str(exc.value) == NF(A2)
    # Then 2
    assert markup_reads(stmts) == 0


# =========================================================================== #
# list_events
# =========================================================================== #

def test_amup_lv_01__every_author_mapped_only_callers_mine(db, S):
    """AMUP-LV-01 — every author's entry, mapped, only the caller's mine.
    Rules: list_events R2."""
    EA = mev(db, S.A1, S.U2, T1)
    EB = mev(db, S.A1, S.U1, T0)
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert sorted(eids(result)) == sorted([EA.id, EB.id])
    # Then 2
    assert {r.id: r.is_mine for r in result} == {EA.id: False, EB.id: True}
    # Then 3
    assert {r.id: r.user_name for r in result} == {EA.id: "Bilal Khan", EB.id: "Ana Rahman"}


def test_amup_lv_02__other_attachments_and_workspaces_not_listed(db, S):
    """AMUP-LV-02 — entries of other attachments (lower and higher id) and other workspaces are not listed.
    Rules: list_events R2."""
    AL = att(db, S, "low.png")
    A2 = att(db, S, "mid.png")
    link(db, S, A2, "scratch", 2)
    AH = att(db, S, "high.png")
    mev(db, AL, S.U1, T1)
    E = mev(db, A2, S.U2, T1)
    mev(db, AH, S.UG, T1)
    _add(db, AttachmentMarkupEvent(
        workspace_id=S.W0.id, attachment_id=A2.id, user_id=S.U1.id, event_type="markup_saved",
        description="seed", created_at=T1))
    _add(db, AttachmentMarkupEvent(
        workspace_id=S.W2.id, attachment_id=A2.id, user_id=S.UG.id, event_type="markup_saved",
        description="seed", created_at=T1))
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U1.id)
    # Then 1
    assert eids(result) == [E.id]


def test_amup_lv_03__newest_first(db, S):
    """AMUP-LV-03 — entries come newest first.
    Rules: list_events R3 (distinct times)."""
    EA = mev(db, S.A1, S.UG, T1)
    EB = mev(db, S.A1, S.U1, T0)
    EC = mev(db, S.A1, S.U2, T2)
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert eids(result) == [EC.id, EA.id, EB.id]


def test_amup_lv_04__ties_highest_id_first_after_update(db, S):
    """AMUP-LV-04 — entries of one time come highest id first, also after an update.
    Rules: list_events R3 [BUG-1436]."""
    seqscan(db)
    EA = mev(db, S.A1, S.UG, T1)
    EB = mev(db, S.A1, S.U1, T1)
    EC = mev(db, S.A1, S.U2, T1)
    touchE(db, EC)
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert eids(result) == [EC.id, EB.id, EA.id]


def test_amup_lv_05__no_entries_empty_list(db, S):
    """AMUP-LV-05 — no entries gives [].
    Rules: list_events R2, R3."""
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert result == []


def test_amup_lv_06__all_201_entries(db, S):
    """AMUP-LV-06 — all 201 entries are returned.
    Rules: list_events R3 [BUG-1437]."""
    db.add_all([
        AttachmentMarkupEvent(
            workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, event_type="markup_saved",
            description="seed", created_at=T1)
        for _ in range(201)
    ])
    db.flush()
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    # Then 1
    assert len(result) == 201


def test_amup_lv_07__soft_deleted_not_found(db, S):
    """AMUP-LV-07 — a soft-deleted attachment raises not found.
    Rules: list_events R1."""
    AD = att(db, S, "gone.png", deleted=True)
    mev(db, AD, S.U1, T1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_events(db, workspace_id=S.W1.id, attachment_id=AD.id, current_user_id=S.U1.id)
    assert str(exc.value) == NF(AD)


def test_amup_lv_08__ready_csv_unavailable(db, S):
    """AMUP-LV-08 — a ready CSV raises unavailable.
    Rules: list_events R1."""
    A2 = att(db, S, "data.csv", mime_type="text/csv", format="csv")
    link(db, S, A2, "scratch", 2)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.list_events(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U1.id)
    assert str(exc.value) == UNAV


@X2115
def test_amup_lv_09__private_project_history_hidden(db, S):
    """AMUP-LV-09 — history of a private project's attachment is hidden from a plain member.
    Rules: list_events R1a [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    mev(db, A2, S.U1, T1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_events(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.UG.id)
    assert str(exc.value) == NF(A2)


@X2115
def test_amup_lv_10__deleted_project_history_hidden(db, S):
    """AMUP-LV-10 — history of a deleted project's attachment is hidden.
    Rules: list_events R1a [BUG-2115]."""
    P = proj(db, S, "Old Job", deleted=True)
    A2 = att(db, S, "old.png")
    link(db, S, A2, "project", P.id)
    mev(db, A2, S.U1, T1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.list_events(db, workspace_id=S.W1.id, attachment_id=A2.id, current_user_id=S.U2.id)
    assert str(exc.value) == NF(A2)


@X2119
def test_amup_lv_11__authors_read_together(db, S):
    """AMUP-LV-11 — authors' profiles are read together.
    Rules: list_events R4 [BUG-2119]."""
    mev(db, S.A1, S.U1, T1)
    mev(db, S.A1, S.U2, T1)
    mev(db, S.A1, S.U1, T0)
    mev(db, S.A1, S.U2, T0)
    mev(db, S.A1, S.U1, T2)
    stmts, stop = recorder(db)
    result = M.list_events(db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.U1.id)
    stop()
    # Then 1
    assert sorted(r.user_name for r in result) == [
        "Ana Rahman", "Ana Rahman", "Ana Rahman", "Bilal Khan", "Bilal Khan"]
    # Then 2
    assert profile_reads(stmts) <= 2


# =========================================================================== #
# put_own_layer
# =========================================================================== #

def test_amup_pl_01__first_save_creates_layer_and_saved_event(db, S):
    """AMUP-PL-01 — a first save creates the layer and a markup_saved event.
    Rules: put_own_layer R3, R6, R7."""
    result = M.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, payload=MP(P1), session_id="tab-1")
    # Then 1
    assert result.user_id == S.U2.id
    assert result.user_name == "Bilal Khan"
    assert result.is_mine is True
    assert result.payload == MP(P1)
    # Then 2
    assert result.updated_at == NOW_DB(db)
    # Then 3
    ls = layers_of(db, S.A1)
    assert len(ls) == 1
    # Then 4
    row = reread(db, AttachmentMarkup, ls[0].id)
    assert row.workspace_id == S.W1.id
    assert row.user_id == S.U2.id
    assert row.payload == D(P1)
    # Then 5
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    # Then 6
    e = reread(db, AttachmentMarkupEvent, evs[0].id)
    assert e.workspace_id == S.W1.id
    assert e.attachment_id == S.A1.id
    assert e.user_id == S.U2.id
    assert e.event_type == "markup_saved"
    assert e.description == "Saved marks on page 1"
    assert e.metadata_json == {"pages": [1]}
    assert e.session_id == "tab-1"


def test_amup_pl_02__first_save_two_pages(db, S):
    """AMUP-PL-02 — a first save of two pages says "Saved marks on pages 1, 2".
    Rules: put_own_layer R3."""
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P12))
    # Then 1
    assert result.is_mine is True
    # Then 2
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    e = evs[0]
    assert e.event_type == "markup_saved"
    assert e.description == "Saved marks on pages 1, 2"
    assert e.metadata_json == {"pages": [1, 2]}
    assert e.session_id is None


def test_amup_pl_03__stored_payload_is_the_dump(db, S):
    """AMUP-PL-03 — the stored payload is the dump: defaults filled in, unknown keys dropped.
    Rules: put_own_layer R3."""
    pl = MarkupPayload.model_validate({"pages": {"1": {"stamps": [STAMPM], "junk": 1}}, "extra": 2})
    M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=pl)
    # Then 1
    ls = layers_of(db, S.A1)
    assert len(ls) == 1
    assert ls[0].payload == pl.model_dump()
    # Then 2
    payload = layers_of(db, S.A1)[0].payload
    assert payload["pages"]["1"]["strokes"] == []
    assert payload["pages"]["1"]["stamps"][0]["rotation"] == 0
    assert "junk" not in payload["pages"]["1"]
    assert "extra" not in payload


def test_amup_pl_04__save_over_existing_replaces_and_updates(db, S):
    """AMUP-PL-04 — saving over an existing layer replaces it and logs markup_updated.
    Rules: put_own_layer R4, R6, R7."""
    L = layer(db, S.A1, S.U1, P1)
    older(db, L, 1)
    result = M.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P2), session_id="tab-2")
    # Then 1
    assert result.payload == MP(P2)
    assert result.updated_at == NOW_DB(db)
    # Then 2
    assert len(layers_of(db, S.A1)) == 1
    # Then 3
    assert reread(db, AttachmentMarkup, L.id).payload == D(P2)
    # Then 4
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    e = evs[0]
    assert e.event_type == "markup_updated"
    assert e.description == "Updated marks on page 2"
    assert e.metadata_json == {"pages": [2]}
    assert e.session_id == "tab-2"
    assert e.user_id == S.U1.id


def test_amup_pl_05__other_users_layers_untouched(db, S):
    """AMUP-PL-05 — other users' layers (lower and higher user id) are untouched.
    Rules: put_own_layer R5."""
    LA = layer(db, S.A1, S.U1, P1)
    LG = layer(db, S.A1, S.UG, P1)
    AH = att(db, S, "high.png")
    LX = layer(db, AH, S.U2, P1)
    M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, payload=MP(P2))
    # Then 1
    assert reread(db, AttachmentMarkup, LA.id).payload == D(P1)
    # Then 2
    assert reread(db, AttachmentMarkup, LG.id).payload == D(P1)
    # Then 3
    assert reread(db, AttachmentMarkup, LX.id).payload == D(P1)
    # Then 4
    assert len(layers_of(db, S.A1)) == 3


def test_amup_pl_06__empty_payload_clears_own_layer(db, S):
    """AMUP-PL-06 — an empty payload deletes the caller's layer and logs markup_cleared.
    Rules: put_own_layer R2."""
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.U2, P1)
    layer(db, S.A1, S.UG, P1)
    result = M.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, payload=MP(EMPTY), session_id="tab-3")
    # Then 1
    assert result is None
    # Then 2
    assert len(layers_of(db, S.A1)) == 2
    # Then 3
    assert uids(layers_of(db, S.A1)) == [S.U1.id, S.UG.id]
    # Then 4
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    e = evs[0]
    assert e.event_type == "markup_cleared"
    assert e.description == "Cleared marks"
    assert e.metadata_json == {"pages": []}
    assert e.session_id == "tab-3"
    assert e.user_id == S.U2.id


def test_amup_pl_07__all_empty_pages_also_clear(db, S):
    """AMUP-PL-07 — only all-empty pages also clear the layer.
    Rules: put_own_layer R2."""
    layer(db, S.A1, S.U1, P1)
    result = M.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(EMPTYPAGE))
    # Then 1
    assert result is None
    # Then 2
    assert len(layers_of(db, S.A1)) == 0
    # Then 3
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_cleared"


def test_amup_pl_08__empty_payload_no_layer_writes_nothing(db, S):
    """AMUP-PL-08 — an empty payload with no layer writes nothing.
    Rules: put_own_layer R2a."""
    layer(db, S.A1, S.U2, P1)
    before = counts(db)
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(EMPTY))
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_09__bare_stroke_is_non_empty_save(db, S):
    """AMUP-PL-09 — a stroke with no points is a non-empty save.
    Rules: put_own_layer R3 (D9)."""
    result = M.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP({"1": {"strokes": [BARE]}}))
    # Then 1
    assert result.is_mine is True
    # Then 2
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    assert evs[0].description == "Saved marks on page 1"


def test_amup_pl_10__unknown_attachment_writes_nothing(db, S):
    """AMUP-PL-10 — an unknown attachment writes nothing.
    Rules: put_own_layer R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=MISSING, user_id=S.U1.id, payload=MP(P1))
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_11__w0_attachment_writes_nothing(db, S):
    """AMUP-PL-11 — a W0 attachment writes nothing.
    Rules: put_own_layer R1."""
    A0 = att(db, S, "zero.png", workspace_id=S.W0.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A0.id, user_id=S.U1.id, payload=MP(P1))
    assert str(exc.value) == NF(A0)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_12__w2_attachment_writes_nothing(db, S):
    """AMUP-PL-12 — a W2 attachment writes nothing.
    Rules: put_own_layer R1."""
    A9 = att(db, S, "far.png", workspace_id=S.W2.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A9.id, user_id=S.U1.id, payload=MP(P1))
    assert str(exc.value) == NF(A9)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_13__pending_attachment_writes_nothing(db, S):
    """AMUP-PL-13 — a pending attachment writes nothing.
    Rules: put_own_layer R1."""
    A2 = att(db, S, "wait.png", upload_status="pending")
    link(db, S, A2, "scratch", 2)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id, payload=MP(P1))
    assert str(exc.value) == UNAV
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_14__not_markable_does_not_clear(db, S):
    """AMUP-PL-14 — a not-markable attachment does not clear an existing layer.
    Rules: put_own_layer R1."""
    A2 = att(db, S, "data.csv", mime_type="text/csv", format="csv")
    link(db, S, A2, "scratch", 2)
    layer(db, A2, S.U1, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id, payload=MP(EMPTY))
    assert str(exc.value) == UNAV
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_15__private_project_refuses_plain_member(db, S):
    """AMUP-PL-15 — a private project's attachment refuses a plain member, nothing written.
    Rules: put_own_layer R1a [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_16__others_ticket_refuses_plain_member(db, S):
    """AMUP-PL-16 — another member's ticket attachment refuses a plain member, nothing written.
    Rules: put_own_layer R1a [BUG-2115]."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_17__deleted_project_refuses_creator(db, S):
    """AMUP-PL-17 — a deleted project's attachment refuses its creator, layer kept.
    Rules: put_own_layer R1a [BUG-2115]."""
    P = proj(db, S, "Old Job", deleted=True)
    A2 = att(db, S, "old.png")
    link(db, S, A2, "project", P.id)
    layer(db, A2, S.U1, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id, payload=MP(EMPTY))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_18__w2_project_refuses(db, S):
    """AMUP-PL-18 — a W2 project's attachment refuses, nothing written.
    Rules: put_own_layer R1a [BUG-2115]."""
    P9 = proj(db, S, "Far Job", where="W2")
    A2 = att(db, S, "far.png")
    link(db, S, A2, "project", P9.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_19__project_id_only_a_ticket_refuses(db, S):
    """AMUP-PL-19 — a project id that exists only as a W1 ticket refuses, nothing written.
    Rules: put_own_layer R1a [BUG-2115]."""
    ticket(db, S, "HT-1", id=XID(3))
    A2 = att(db, S, "x.png")
    link(db, S, A2, "project", XID(3))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_pl_20__project_member_saves_on_private(db, S):
    """AMUP-PL-20 — a project member saves on the private project's attachment.
    Rules: put_own_layer R1a (granted side of BUG-2115), R3."""
    P = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P, S.UG)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id, payload=MP(P1))
    # Then 1
    assert result.user_id == S.UG.id
    # Then 2
    assert len(layers_of(db, A2)) == 1


@X2115
def test_amup_pl_21__hidden_and_pending_not_found(db, S):
    """AMUP-PL-21 — a hidden attachment that is also pending answers not found.
    Rules: put_own_layer R1a [BUG-2115] (before R3 / R4 of the helper)."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "wait.png", upload_status="pending")
    link(db, S, A2, "project", P.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted


def test_amup_pl_22__same_payload_returns_layer_unchanged(db, S):
    """AMUP-PL-22 — saving the stored payload again returns the layer unchanged.
    Rules: put_own_layer R6, R7a (part that holds today)."""
    L = layer(db, S.A1, S.U1, P1)
    older(db, L, 1)
    db.refresh(L)
    t0 = L.updated_at
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    # Then 1
    assert result.payload == MP(P1)
    assert result.updated_at == t0
    # Then 2
    assert len(layers_of(db, S.A1)) == 1


@X2118
def test_amup_pl_23__same_payload_writes_no_event(db, S):
    """AMUP-PL-23 — saving the stored payload again writes no event.
    Rules: put_own_layer R7a [BUG-2118]."""
    layer(db, S.A1, S.U1, P1)
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    # Then 1
    assert result.user_id == S.U1.id
    # Then 2
    assert len(events_of(db, S.A1)) == 0


@X2118
def test_amup_pl_24__save_twice_one_event(db, S):
    """AMUP-PL-24 — a save then the same save again leaves one event.
    Rules: put_own_layer R7a [BUG-2118]."""
    M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    # Then 1
    assert result.payload == MP(P1)
    # Then 2
    assert len(events_of(db, S.A1)) == 1


@X2120
def test_amup_pl_25__concurrent_first_save_becomes_update(db, S):
    """AMUP-PL-25 — a concurrent first save becomes an update, no error.
    Rules: put_own_layer R5a [BUG-2120]."""
    L = layer(db, S.A1, S.U1, P1)
    with patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None):
        sp = db.begin_nested()
        try:
            result = M.put_own_layer(
                db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P2))
        except Exception:
            sp.rollback()
            raise
        sp.commit()
    # Then 1
    assert result.payload == MP(P2)
    # Then 2
    assert len(layers_of(db, S.A1)) == 1
    # Then 3
    assert reread(db, AttachmentMarkup, L.id).payload == D(P2)
    # Then 4
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_updated"


def test_amup_pl_26__flushes_never_commits(db, S):
    """AMUP-PL-26 — put_own_layer flushes, never commits.
    Rules: put_own_layer Side effects (no commit)."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(layers_of(db, S.A1)) == 0
    # Then 3
    assert len(events_of(db, S.A1)) == 0


def test_amup_pl_27__returned_layer_carries_current_stamp(db, S):
    """AMUP-PL-27 — the returned layer carries the author's current stamp.
    Rules: put_own_layer R6; _resolve_saved_stamp R1 (D6)."""
    stamp(db, S.U1, VEC)
    result = M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    # Then 1
    assert result.saved_stamp == VEC
    assert result.user_name == "Ana Rahman"


@X2115
def test_amup_pl_28__no_link_writes_nothing(db, S):
    """AMUP-PL-28 — an attachment with no link writes nothing.
    Rules: put_own_layer R1a [BUG-2115]; PR-3 (no own-workspace link)."""
    A2 = att(db, S, "lonely.png")
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_pl_29__suspended_owner_refused_private(db, S):
    """AMUP-PL-29 — a suspended owner-role member is refused a private project's attachment, nothing written.
    Rules: put_own_layer R1a [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "owner", status="suspended")
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id, payload=MP(P1))
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


# =========================================================================== #
# delete_own_layer
# =========================================================================== #

def test_amup_pl_30__w2_filed_own_row_never_replaced(db, S):
    """AMUP-PL-30 — the caller's markup row filed under W2 on the same attachment is never replaced.
    Rules: put_own_layer R5, R4; HR-16."""
    LW = layer(db, S.A1, S.U1, P2, ws=S.W2)
    sp = db.begin_nested()
    try:
        M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id, payload=MP(P1))
    except IntegrityError:
        sp.rollback()
    else:
        sp.commit()
    # Then 1
    row = reread(db, AttachmentMarkup, LW.id)
    assert row.workspace_id == S.W2.id
    assert row.payload == D(P2)
    # Then 2
    n_w2 = db.execute(select(func.count()).select_from(AttachmentMarkup).where(
        AttachmentMarkup.attachment_id == S.A1.id, AttachmentMarkup.workspace_id == S.W2.id)).scalar_one()
    assert n_w2 == 1
    # Then 3
    assert len([e for e in events_of(db, S.A1) if e.event_type == "markup_updated"]) == 0


def test_amup_pl_31__only_leading_updated_marks_replaced(db, S):
    """AMUP-PL-31 — only the leading "Updated marks" becomes "Saved marks".
    Rules: put_own_layer R3 (G5); _summarize_payload R2, R4."""
    M.put_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id,
                    payload=MP({"Updated marks": {"strokes": [STROKE]}}))
    # Then 1
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    # Then 2
    e = reread(db, AttachmentMarkupEvent, evs[0].id)
    assert e.event_type == "markup_saved"
    assert e.description == "Saved marks on page Updated marks"
    assert e.metadata_json == {"pages": ["Updated marks"]}


def test_amup_dl_01__own_layer_deleted_and_cleared_logged(db, S):
    """AMUP-DL-01 — the caller's layer is deleted and markup_cleared is logged.
    Rules: delete_own_layer R2, R4."""
    LA = layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.U2, P1)
    layer(db, S.A1, S.UG, P1)
    result = M.delete_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id, session_id="tab-4")
    # Then 1
    assert result is None
    # Then 2
    assert uids(layers_of(db, S.A1)) == [S.U1.id, S.UG.id]
    # Then 3
    assert reread(db, AttachmentMarkup, LA.id).payload == D(P1)
    # Then 4
    evs = events_of(db, S.A1)
    assert len(evs) == 1
    e = evs[0]
    assert e.workspace_id == S.W1.id
    assert e.user_id == S.U2.id
    assert e.event_type == "markup_cleared"
    assert e.description == "Cleared marks"
    assert e.metadata_json == {"pages": []}
    assert e.session_id == "tab-4"


def test_amup_dl_02__no_own_layer_nothing_happens(db, S):
    """AMUP-DL-02 — no own layer: nothing deleted, no event, no error.
    Rules: delete_own_layer R3, R4."""
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.UG, P1)
    before = counts(db)
    result = M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_03__own_layer_on_other_attachment_kept(db, S):
    """AMUP-DL-03 — the caller's layer on another attachment is not deleted.
    Rules: delete_own_layer R2, R3."""
    AH = att(db, S, "high.png")
    LX = layer(db, AH, S.U1, P1)
    result = M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert reread(db, AttachmentMarkup, LX.id).payload == D(P1)
    # Then 3
    assert len(events_of(db, S.A1)) == 0


def test_amup_dl_04__unknown_attachment_deletes_nothing(db, S):
    """AMUP-DL-04 — an unknown attachment deletes nothing.
    Rules: delete_own_layer R1."""
    layer(db, S.A1, S.U1, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=MISSING, user_id=S.U1.id)
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_05__soft_deleted_keeps_layer(db, S):
    """AMUP-DL-05 — a soft-deleted attachment keeps its layer.
    Rules: delete_own_layer R1."""
    AD = att(db, S, "gone.png", deleted=True)
    layer(db, AD, S.U1, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=AD.id, user_id=S.U1.id)
    assert str(exc.value) == NF(AD)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_06__w2_attachment_keeps_layer(db, S):
    """AMUP-DL-06 — a W2 attachment keeps its layer.
    Rules: delete_own_layer R1."""
    A9 = att(db, S, "far.png", workspace_id=S.W2.id)
    _add(db, AttachmentMarkup(workspace_id=S.W2.id, attachment_id=A9.id, user_id=S.U1.id, payload=D(P1)))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A9.id, user_id=S.U1.id)
    assert str(exc.value) == NF(A9)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_07__failed_attachment_keeps_layer(db, S):
    """AMUP-DL-07 — a failed attachment keeps its layer.
    Rules: delete_own_layer R1."""
    A2 = att(db, S, "bad.png", upload_status="failed")
    link(db, S, A2, "scratch", 2)
    layer(db, A2, S.U1, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id)
    assert str(exc.value) == UNAV
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_dl_08__private_project_refuses_plain_member(db, S):
    """AMUP-DL-08 — a private project's attachment refuses a plain member, layer kept.
    Rules: delete_own_layer R1a [BUG-2115]."""
    P = proj(db, S, "Tender 7", private=True)
    A2 = att(db, S, "contract.png")
    link(db, S, A2, "project", P.id)
    layer(db, A2, S.UG, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_dl_09__others_ticket_refuses(db, S):
    """AMUP-DL-09 — another member's ticket attachment refuses, layer kept.
    Rules: delete_own_layer R1a [BUG-2115]."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    layer(db, A2, S.UG, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.UG.id)
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


@X2115
def test_amup_dl_10__component_of_deleted_project_refuses(db, S):
    """AMUP-DL-10 — a component of a deleted project refuses, layer kept.
    Rules: delete_own_layer R1a [BUG-2115]."""
    P = proj(db, S, "Old Job", deleted=True)
    C = comp(db, P, "Roof")
    A2 = att(db, S, "roof.png")
    link(db, S, A2, "project_component", C.id)
    layer(db, A2, S.U2, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U2.id)
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_11__ticket_creator_clears_own_layer(db, S):
    """AMUP-DL-11 — the ticket's creator clears their layer on its attachment.
    Rules: delete_own_layer R1a (granted side of BUG-2115), R2."""
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    layer(db, A2, S.U1, P1)
    result = M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=S.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(layers_of(db, A2)) == 0


def test_amup_dl_12__flushes_never_commits(db, S):
    """AMUP-DL-12 — delete_own_layer flushes, never commits.
    Rules: delete_own_layer Side effects (no commit)."""
    layer(db, S.A1, S.U1, P1)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert len(layers_of(db, S.A1)) == 1
    # Then 3
    assert len(events_of(db, S.A1)) == 0


@X2115
def test_amup_dl_13__inactive_owner_refused_others_ticket(db, S):
    """AMUP-DL-13 — a removed (inactive) owner-role member is refused another member's ticket, layer kept.
    Rules: delete_own_layer R1a [BUG-2115]; PR-5 (active membership only)."""
    U3 = make_profile(db, name="Rafi Das")
    member(db, S, U3, "owner", status="inactive")
    T = ticket(db, S, "HT-1")
    A2 = att(db, S, "shot.png")
    link(db, S, A2, "support_ticket", T.id)
    layer(db, A2, U3, P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=A2.id, user_id=U3.id)
    assert str(exc.value) == NF(A2)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert counts(db) == before


def test_amup_dl_14__w2_filed_own_row_not_deleted(db, S):
    """AMUP-DL-14 — the caller's markup row filed under W2 on the same attachment is not deleted.
    Rules: delete_own_layer R3, R4; HR-16."""
    LW = layer(db, S.A1, S.U1, P2, ws=S.W2)
    result = M.delete_own_layer(db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    row = reread(db, AttachmentMarkup, LW.id)
    assert row.workspace_id == S.W2.id
    assert row.payload == D(P2)
    # Then 4
    assert len(events_of(db, S.A1)) == 0
