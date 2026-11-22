"""Unit tests for app/services/attachment_markup_service.py.

Implements tests/unit/services/attachment_markup_service.cases.md (revision 2),
one test per card, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything.

Nothing external is patched (the spec names no external). Every test sets the
Cloudinary / environment settings of the Conventions on
`app.core.config.settings` (autouse fixture). Patched, as Conventions name them:
the commit / rollback spies and the failing commit (both still call the real
rollback), PL-05's order log (wraps the real commit and refresh) and PL-10's race
simulation (`AttachmentMarkupDAO.get_for_user` returns None).

Every test builds the Standing rows (fixture `S`, attributes named as in the
cards: `S.W1`, `S.UG`, `S.A1` ...), adds its Given rows one flush each, then runs
the commit point (`commit_point`: `db.commit()` and the "nothing written"
snapshot). `# [claude] <ID>` marks each test; `# Then N` marks the checks of the
card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text

from app.core.config import settings
from app.managers.attachment_manager import (
    AttachmentNotFoundError,
    AttachmentValidationError,
)
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink
from app.models.attachment_markup import AttachmentMarkup
from app.models.attachment_markup_event import AttachmentMarkupEvent
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.workspace_member import WorkspaceMember
from app.schemas.attachment_markup import MarkupPayload
from app.services.attachment_markup_service import attachment_markup_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc"
svc = attachment_markup_service

# Convention "MISSING"
MISSING = 999999999

# Conventions T0, T1, T2 (naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)

# Convention "UNAV"
UNAV = "Markup is only available for images and PDFs."


# Convention "NFA(A)"
def NFA(a):
    return "Attachment " + str(a.id) + " not found."


# Conventions "Payloads"
PT = {"x": 0.1, "y": 0.2}
STROKE = {"color": "#ff0000", "width": 0.5, "points": [PT]}
TEXT = {"x": 0.1, "y": 0.1, "text": "OK", "color": "#000000", "size": 0.05}
P1 = {"1": {"strokes": [STROKE]}}
P2 = {"2": {"texts": [TEXT]}}
EMPTY = {}


def MP(d):
    return MarkupPayload.model_validate({"pages": d})


def D(d):
    return MP(d).model_dump()


# xfail markers (reason = bug id and title, docs/testing/bugs.md)
X2115 = pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-2115: any member sees and draws marks on attachments of a private project "
        "or another member's help ticket"
    ),
)
X2118 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2118: saving unchanged marks writes a markup_updated history entry",
)
X2119 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2119: markup layers and history read the author's profile once or twice per row",
)
X2120 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2120: two first saves of one user's layer at once: the second answers 500",
)


# --------------------------------------------------------------------------- #
# Settings (every test)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def amsv_settings(monkeypatch):
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
    return _add(
        db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status)
    )


# Given row "att(name)"; `ws` = "W0 att"; `over` = the columns after "but"
def att(db, S, name, ws=None, **over):
    fields = {
        "workspace_id": (ws or S.W1).id,
        "file_name": name,
        "mime_type": "image/png",
        "file_size": 100,
        "uploaded_by": S.U1.id,
        "upload_status": "ready",
        "format": "png",
    }
    fields.update(over)
    return _add(db, Attachment(**fields))


# Given row "link(A, type, eid)"
def link(db, S, a, etype, eid):
    return _add(
        db,
        AttachmentLink(
            workspace_id=a.workspace_id,
            attachment_id=a.id,
            entity_type=etype,
            entity_id=eid,
            linked_by=S.U1.id,
        ),
    )


# Standing rows (every test, in this order, flushed)
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
    s.F0 = _add(
        db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0")
    )
    s.F1 = _add(
        db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1")
    )
    s.F9 = _add(
        db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9")
    )
    s.A1 = att(db, s, "plan.png")
    link(db, s, s.A1, "scratch", 1)
    return s


# Given row "proj(name)"; `private` = "but private"
def proj(db, S, name, private=False):
    return _add(
        db,
        Project(
            workspace_id=S.W1.id,
            factory_id=S.F1.id,
            name=name,
            description="Main",
            created_by=S.U1.id,
            visibility="invited_only" if private else "workspace",
        ),
    )


# Given row "pmem(P, U)"
def pmem(db, S, p, u):
    return _add(
        db,
        ProjectMember(
            workspace_id=p.workspace_id,
            project_id=p.id,
            user_id=u.id,
            assigned_by=S.U1.id,
        ),
    )


# Given row "ticket(n)"
def ticket(db, S, n):
    return _add(
        db,
        HelpTicket(
            workspace_id=S.W1.id,
            ticket_number=n,
            title="Printer jam",
            description="It jams",
            created_by=S.U1.id,
        ),
    )


# Given row "layer(A, U, P)"
def layer(db, a, u, p):
    return _add(
        db,
        AttachmentMarkup(
            workspace_id=a.workspace_id, attachment_id=a.id, user_id=u.id, payload=D(p)
        ),
    )


# Given row "mev(A, U, at)"
def mev(db, a, u, at):
    return _add(
        db,
        AttachmentMarkupEvent(
            workspace_id=a.workspace_id,
            attachment_id=a.id,
            user_id=u.id,
            event_type="markup_saved",
            description="seed",
            created_at=at,
        ),
    )


# Given row "older(X, h)"
def older(db, x, h):
    db.execute(
        text(
            "UPDATE attachment_markups SET updated_at = now() - make_interval(hours => :h) "
            "WHERE id = :i"
        ),
        {"h": h, "i": x.id},
    )
    db.expire_all()


# --------------------------------------------------------------------------- #
# Conventions -> commit point and named checks
# --------------------------------------------------------------------------- #


# Convention "nothing written": row counts of both tables, all workspaces
def counts(db):
    return (
        db.scalar(select(func.count()).select_from(AttachmentMarkup)),
        db.scalar(select(func.count()).select_from(AttachmentMarkupEvent)),
    )


# Convention "Commit point": db.commit(); snapshots are taken there
def commit_point(db):
    db.commit()
    return counts(db)


# Convention "pending X"; returns X_ID
def pending_x(db, S):
    x = Factory(workspace_id=S.W2.id, name="Factory X", abbreviation="FX")
    db.add(x)
    db.flush()
    return x.id


def _x_count(db, x_id):
    return db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": x_id})


# Convention "x_gone"
def x_gone(db, x_id):
    return _x_count(db, x_id) == 0


# Convention "x_kept"
def x_kept(db, x_id):
    return _x_count(db, x_id) == 1


# Convention "re-read X" (layer)
def reread_layer(db, layer_id):
    db.expire_all()
    return db.execute(
        select(AttachmentMarkup).where(AttachmentMarkup.id == layer_id)
    ).scalar_one_or_none()


# Convention "layers_of(A)"
def layers_of(db, a_id):
    db.expire_all()
    return list(
        db.execute(
            select(AttachmentMarkup)
            .where(AttachmentMarkup.attachment_id == a_id)
            .order_by(AttachmentMarkup.id)
        ).scalars()
    )


# Convention "events_of(A)"
def events_of(db, a_id):
    db.expire_all()
    return list(
        db.execute(
            select(AttachmentMarkupEvent)
            .where(AttachmentMarkupEvent.attachment_id == a_id)
            .order_by(AttachmentMarkupEvent.id)
        ).scalars()
    )


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "failing commit" (the rollback spy wraps the real method)
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "recorder": start; `stop_recorder` removes the listener right after the When
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, parameters, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, (conn, rec)


def stop_recorder(handle):
    conn, rec = handle
    event.remove(conn, "before_cursor_execute", rec)


# Convention "profile_reads"
def profile_reads(stmts):
    return sum(
        1
        for s in stmts
        if s.lstrip().upper().startswith("SELECT") and "FROM profiles" in s
    )


# Convention "pairs(r)"
def pairs(r):
    return {(i.user_id, i.is_mine) for i in r.items}


# Convention "Race simulations" (AMSV-PL-10)
def race():
    return patch(
        "app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None
    )


# =========================================================================== #
# AttachmentMarkupService.list_layers
# =========================================================================== #


# [claude] AMSV-LL-01
def test_amsv_ll_01__every_authors_layer_only_callers_marked_mine(db, S):
    """AMSV-LL-01 — every author's layer is listed, only the caller's marked mine.
    Rules: list_layers R1."""
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.UG, P2)
    commit_point(db)

    result = svc.list_layers(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert type(result).__name__ == "AttachmentMarkupListResponse"
    # Then 2
    assert pairs(result) == {(S.U1.id, False), (S.UG.id, True)}
    # Then 3
    assert {i.user_name for i in result.items} == {"Ana Rahman", "Mia Khan"}
    # Then 4
    assert len(result.items) == 2


# [claude] AMSV-LL-02
def test_amsv_ll_02__no_layers_gives_empty_list(db, S):
    """AMSV-LL-02 — an attachment with no layers gives [].
    Rules: list_layers R1."""
    commit_point(db)

    result = svc.list_layers(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert result.items == []


# [claude] AMSV-LL-03
def test_amsv_ll_03__the_read_commits_a_pending_change(db, S):
    """AMSV-LL-03 — the read commits: a change pending in the session is saved.
    Rules: list_layers R2 (D1)."""
    layer(db, S.A1, S.U1, P1)
    before = commit_point(db)
    x_id = pending_x(db, S)

    with spies(db) as (cm, rb):
        result = svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
        )

    # Then 1
    assert pairs(result) == {(S.U1.id, False)}
    # Then 2
    assert cm.call_count == 1
    assert rb.called is False
    # Then 3
    db.rollback()
    assert x_kept(db, x_id)
    # Then 4
    assert counts(db) == before


# [claude] AMSV-LL-04
def test_amsv_ll_04__unknown_attachment_rolls_back(db, S):
    """AMSV-LL-04 — an unknown attachment raises not found, rolls back and discards pending changes.
    Rules: list_layers R3, TC3."""
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with spies(db) as (cm, rb):
        with pytest.raises(AttachmentNotFoundError) as exc:
            svc.list_layers(
                db, workspace_id=S.W1.id, attachment_id=MISSING, current_user_id=S.UG.id
            )
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    assert cm.called is False
    # Then 5
    assert x_gone(db, x_id)


# [claude] AMSV-LL-05
def test_amsv_ll_05__pending_attachment_raises_unavailable(db, S):
    """AMSV-LL-05 — a pending attachment raises unavailable and rolls back.
    Rules: list_layers R3, TC3."""
    a2 = att(db, S, "draft.png", upload_status="pending")
    link(db, S, a2, "scratch", 1)
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == UNAV
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)


# [claude] AMSV-LL-06
def test_amsv_ll_06__w0_attachment_is_not_found(db, S):
    """AMSV-LL-06 — a W0 attachment is not found from W1.
    Rules: list_layers R3; HR-16."""
    a0 = att(db, S, "w0.png", ws=S.W0)
    link(db, S, a0, "scratch", 1)
    layer(db, a0, S.UG, P1)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=a0.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a0)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] AMSV-LL-07
@X2115
def test_amsv_ll_07__private_project_layers_hidden_from_plain_member(db, S):
    """AMSV-LL-07 — layers on a private project's attachment are hidden from a plain member.
    Rules: list_layers R3 [BUG-2115]; PR-3, PR-5."""
    p = proj(db, S, "Tender", private=True)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    layer(db, a2, S.U1, P1)
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)


# [claude] AMSV-LL-08
@X2115
def test_amsv_ll_08__other_private_project_membership_does_not_open(db, S):
    """AMSV-LL-08 — membership of another private project does not open this one.
    Rules: list_layers R3 [BUG-2115]; PR-2."""
    p = proj(db, S, "Tender", private=True)
    q = proj(db, S, "Bridge", private=True)
    pmem(db, S, q, S.UG)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] AMSV-LL-09
@X2115
def test_amsv_ll_09__owner_role_in_w2_does_not_open_w1_ticket(db, S):
    """AMSV-LL-09 — an owner role held only in W2 does not open another member's W1 ticket.
    Rules: list_layers R3 [BUG-2115]; PR-2, PR-5."""
    member(db, S, S.UG, "owner", ws=S.W2)
    t = ticket(db, S, "HT-1")
    a2 = att(db, S, "ticket.png")
    link(db, S, a2, "support_ticket", t.id)
    commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_layers(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# [claude] AMSV-LL-10
def test_amsv_ll_10__project_member_lists_private_project_layers(db, S):
    """AMSV-LL-10 — a project member lists the private project's layers.
    Rules: list_layers R1; PR-2, PR-5."""
    p = proj(db, S, "Tender", private=True)
    pmem(db, S, p, S.UG)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    layer(db, a2, S.U1, P1)
    commit_point(db)

    result = svc.list_layers(
        db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
    )

    # Then 1
    assert pairs(result) == {(S.U1.id, False)}


# [claude] AMSV-LL-11
@X2119
def test_amsv_ll_11__authors_profiles_are_read_together(db, S):
    """AMSV-LL-11 — the authors' profiles of a layer list are read together.
    Rules: list_layers Returns (manager R4) [BUG-2119]."""
    u3 = make_profile(db, name="Lena Roy")
    u4 = make_profile(db, name="Omar Ali")
    u5 = make_profile(db, name="Nila Sen")
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.U2, P1)
    layer(db, S.A1, u3, P1)
    layer(db, S.A1, u4, P1)
    layer(db, S.A1, u5, P1)
    commit_point(db)
    # recorder: started after the commit point, with the ids read first, so only the
    # When's own statements are recorded (the commit expires S.U1; reading its id would
    # otherwise add one profile SELECT that is not the service's)
    w1_id, a1_id, u1_id = S.W1.id, S.A1.id, S.U1.id
    stmts, handle = recorder(db)

    result = svc.list_layers(
        db, workspace_id=w1_id, attachment_id=a1_id, current_user_id=u1_id
    )
    stop_recorder(handle)

    # Then 1
    assert sorted(i.user_name for i in result.items) == [
        "Ana Rahman",
        "Bilal Khan",
        "Lena Roy",
        "Nila Sen",
        "Omar Ali",
    ]
    # Then 2
    assert profile_reads(stmts) <= 2


# [claude] AMSV-LL-12
def test_amsv_ll_12__managers_order_oldest_update_first_is_kept(db, S):
    """AMSV-LL-12 — the manager's order (oldest update first) is kept.
    Rules: list_layers R1 (in its order)."""
    l1 = layer(db, S.A1, S.U1, P1)
    l2 = layer(db, S.A1, S.U2, P1)
    l3 = layer(db, S.A1, S.UG, P1)
    older(db, l1, 2)
    older(db, l2, 3)
    older(db, l3, 1)
    commit_point(db)

    result = svc.list_layers(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert [i.user_id for i in result.items] == [S.U2.id, S.U1.id, S.UG.id]


# =========================================================================== #
# AttachmentMarkupService.list_events
# =========================================================================== #


# [claude] AMSV-LV-01
def test_amsv_lv_01__every_history_entry_only_callers_marked_mine(db, S):
    """AMSV-LV-01 — every history entry is listed, only the caller's marked mine.
    Rules: list_events R1."""
    e1 = mev(db, S.A1, S.U1, T1)
    e2 = mev(db, S.A1, S.UG, T2)
    commit_point(db)

    result = svc.list_events(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert type(result).__name__ == "AttachmentMarkupEventListResponse"
    # Then 2
    assert {(i.id, i.is_mine) for i in result.items} == {(e1.id, False), (e2.id, True)}
    # Then 3
    assert {i.event_type for i in result.items} == {"markup_saved"}


# [claude] AMSV-LV-02
def test_amsv_lv_02__no_history_gives_empty_list(db, S):
    """AMSV-LV-02 — an attachment with no history gives [].
    Rules: list_events R1."""
    commit_point(db)

    result = svc.list_events(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert result.items == []


# [claude] AMSV-LV-03
def test_amsv_lv_03__the_read_commits_a_pending_change(db, S):
    """AMSV-LV-03 — the history read commits: a change pending in the session is saved.
    Rules: list_events R2 (D1)."""
    mev(db, S.A1, S.U1, T1)
    commit_point(db)
    x_id = pending_x(db, S)

    with spies(db) as (cm, rb):
        result = svc.list_events(
            db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
        )

    # Then 1
    assert len(result.items) == 1
    # Then 2
    assert cm.call_count == 1
    assert rb.called is False
    # Then 3
    db.rollback()
    assert x_kept(db, x_id)


# [claude] AMSV-LV-04
def test_amsv_lv_04__unknown_attachment_rolls_back(db, S):
    """AMSV-LV-04 — an unknown attachment raises not found, rolls back and discards pending changes.
    Rules: list_events R2, TC3."""
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with spies(db) as (cm, rb):
        with pytest.raises(AttachmentNotFoundError) as exc:
            svc.list_events(
                db, workspace_id=S.W1.id, attachment_id=MISSING, current_user_id=S.UG.id
            )
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    assert cm.called is False
    # Then 5
    assert x_gone(db, x_id)


# [claude] AMSV-LV-05
@X2115
def test_amsv_lv_05__private_project_history_hidden_from_plain_member(db, S):
    """AMSV-LV-05 — history of a private project's attachment is hidden from a plain member.
    Rules: list_events R2 [BUG-2115]; PR-3, PR-5."""
    p = proj(db, S, "Tender", private=True)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    mev(db, a2, S.U1, T1)
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.list_events(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)


# [claude] AMSV-LV-06
@X2119
def test_amsv_lv_06__authors_profiles_are_read_together(db, S):
    """AMSV-LV-06 — the authors' profiles of the history are read together.
    Rules: list_events Returns (manager R4) [BUG-2119]."""
    mev(db, S.A1, S.U1, T1)
    mev(db, S.A1, S.U2, T1)
    mev(db, S.A1, S.UG, T1)
    mev(db, S.A1, S.U1, T2)
    mev(db, S.A1, S.U2, T2)
    commit_point(db)
    # recorder: as AMSV-LL-11, only the When's statements
    w1_id, a1_id, ug_id = S.W1.id, S.A1.id, S.UG.id
    stmts, handle = recorder(db)

    result = svc.list_events(
        db, workspace_id=w1_id, attachment_id=a1_id, current_user_id=ug_id
    )
    stop_recorder(handle)

    # Then 1
    assert len(result.items) == 5
    # Then 2
    assert profile_reads(stmts) <= 2


# [claude] AMSV-LV-07
def test_amsv_lv_07__pending_attachment_raises_unavailable(db, S):
    """AMSV-LV-07 — a pending attachment raises unavailable and rolls back.
    Rules: list_events R2, TC3."""
    a2 = att(db, S, "draft.png", upload_status="pending")
    link(db, S, a2, "scratch", 1)
    commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.list_events(
            db, workspace_id=S.W1.id, attachment_id=a2.id, current_user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == UNAV
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)


# [claude] AMSV-LV-08
def test_amsv_lv_08__managers_order_newest_first_is_kept(db, S):
    """AMSV-LV-08 — the manager's order (newest first) is kept.
    Rules: list_events R1 (in its order)."""
    e1 = mev(db, S.A1, S.U1, T2)
    e2 = mev(db, S.A1, S.U2, T1)
    e3 = mev(db, S.A1, S.UG, datetime(2026, 1, 1, 11, 0, 0))
    commit_point(db)

    result = svc.list_events(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, current_user_id=S.UG.id
    )

    # Then 1
    assert [i.id for i in result.items] == [e3.id, e1.id, e2.id]


# =========================================================================== #
# AttachmentMarkupService.put_own_layer
# =========================================================================== #


# [claude] AMSV-PL-01
def test_amsv_pl_01__first_save_committed_with_markup_saved(db, S):
    """AMSV-PL-01 — a first save is committed with a markup_saved event.
    Rules: put_own_layer R1, R2, TC1."""
    commit_point(db)

    result = svc.put_own_layer(
        db,
        workspace_id=S.W1.id,
        attachment_id=S.A1.id,
        user_id=S.UG.id,
        payload=MP(P1),
        session_id="s-1",
    )

    # Then 1
    assert type(result).__name__ == "AttachmentMarkupLayerResponse"
    # Then 2
    assert result.user_id == S.UG.id
    assert result.is_mine is True
    assert result.payload == MP(P1)
    # Then 3
    db.rollback()
    rows = layers_of(db, S.A1.id)
    assert len(rows) == 1
    assert rows[0].user_id == S.UG.id
    assert rows[0].payload == D(P1)
    # Then 4
    evs = events_of(db, S.A1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_saved"
    assert evs[0].user_id == S.UG.id
    assert evs[0].session_id == "s-1"
    assert evs[0].description == "Saved marks on page 1"


# [claude] AMSV-PL-02
def test_amsv_pl_02__save_over_existing_layer_committed_with_markup_updated(db, S):
    """AMSV-PL-02 — saving over an existing layer is committed with markup_updated.
    Rules: put_own_layer R1, TC1."""
    lay = layer(db, S.A1, S.UG, P1)
    commit_point(db)
    l_id = lay.id

    result = svc.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.UG.id, payload=MP(P2)
    )

    # Then 1
    assert result.payload == MP(P2)
    # Then 2
    db.rollback()
    row = reread_layer(db, l_id)
    assert row.payload == D(P2)
    # Then 3
    evs = events_of(db, S.A1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_updated"
    assert evs[0].description == "Updated marks on page 2"


# [claude] AMSV-PL-03
def test_amsv_pl_03__empty_payload_clears_layer_and_returns_none(db, S):
    """AMSV-PL-03 — an empty payload clears the layer, commits markup_cleared and returns None.
    Rules: put_own_layer R1, Returns (None), TC1."""
    layer(db, S.A1, S.UG, P1)
    commit_point(db)

    result = svc.put_own_layer(
        db,
        workspace_id=S.W1.id,
        attachment_id=S.A1.id,
        user_id=S.UG.id,
        payload=MP(EMPTY),
        session_id="s-2",
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert len(layers_of(db, S.A1.id)) == 0
    # Then 3
    evs = events_of(db, S.A1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_cleared"
    assert evs[0].description == "Cleared marks"
    assert evs[0].metadata_json == {"pages": []}
    assert evs[0].session_id == "s-2"


# [claude] AMSV-PL-04
def test_amsv_pl_04__empty_payload_without_layer_writes_nothing(db, S):
    """AMSV-PL-04 — an empty payload with no own layer returns None and writes nothing.
    Rules: put_own_layer R1, Returns (None)."""
    layer(db, S.A1, S.U1, P1)
    before = commit_point(db)

    result = svc.put_own_layer(
        db,
        workspace_id=S.W1.id,
        attachment_id=S.A1.id,
        user_id=S.UG.id,
        payload=MP(EMPTY),
    )

    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before
    # Then 3
    db.rollback()
    rows = layers_of(db, S.A1.id)
    assert len(rows) == 1
    assert rows[0].user_id == S.U1.id


# [claude] AMSV-PL-05
def test_amsv_pl_05__returned_layer_not_reread_after_commit(db, S):
    """AMSV-PL-05 — the returned layer is not re-read after the commit.
    Rules: put_own_layer R2."""
    commit_point(db)
    calls = []
    real_c, real_r = db.commit, db.refresh

    with (
        patch.object(
            db, "commit", side_effect=lambda: (calls.append("commit"), real_c())[1]
        ),
        patch.object(
            db,
            "refresh",
            side_effect=lambda *a, **k: (calls.append("refresh"), real_r(*a, **k))[1],
        ),
    ):
        result = svc.put_own_layer(
            db,
            workspace_id=S.W1.id,
            attachment_id=S.A1.id,
            user_id=S.UG.id,
            payload=MP(P1),
        )

    # Then 1
    assert result.payload == MP(P1)
    # Then 2
    assert calls.count("commit") == 1
    # Then 3
    assert "refresh" not in calls[calls.index("commit") :]
    # Then 4
    db.rollback()
    assert result.updated_at == layers_of(db, S.A1.id)[0].updated_at


# [claude] AMSV-PL-06
def test_amsv_pl_06__unknown_attachment_rolls_back(db, S):
    """AMSV-PL-06 — an unknown attachment raises not found, rolls back and discards pending changes.
    Rules: put_own_layer R3, TC3."""
    before = commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with spies(db) as (cm, rb):
        with pytest.raises(AttachmentNotFoundError) as exc:
            svc.put_own_layer(
                db,
                workspace_id=S.W1.id,
                attachment_id=MISSING,
                user_id=S.UG.id,
                payload=MP(P1),
            )
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    assert cm.called is False
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


# [claude] AMSV-PL-07
def test_amsv_pl_07__failing_commit_leaves_no_layer_and_no_event(db, S):
    """AMSV-PL-07 — a failing commit leaves no layer and no event.
    Rules: put_own_layer R3, TC4."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.put_own_layer(
                db,
                workspace_id=S.W1.id,
                attachment_id=S.A1.id,
                user_id=S.UG.id,
                payload=MP(P1),
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# [claude] AMSV-PL-08
@X2115
def test_amsv_pl_08__private_project_refuses_plain_member(db, S):
    """AMSV-PL-08 — a private project's attachment refuses a plain member; nothing written.
    Rules: put_own_layer R1, R3 [BUG-2115]; PR-3, PR-5."""
    p = proj(db, S, "Tender", private=True)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    before = commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.put_own_layer(
            db,
            workspace_id=S.W1.id,
            attachment_id=a2.id,
            user_id=S.UG.id,
            payload=MP(P1),
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] AMSV-PL-09
@X2115
def test_amsv_pl_09__owner_role_in_w0_does_not_open_w1_ticket(db, S):
    """AMSV-PL-09 — an owner role held only in W0 does not open another member's W1 ticket.
    Rules: put_own_layer R3 [BUG-2115]; PR-2, PR-5."""
    member(db, S, S.UG, "owner", ws=S.W0)
    t = ticket(db, S, "HT-1")
    a2 = att(db, S, "ticket.png")
    link(db, S, a2, "support_ticket", t.id)
    before = commit_point(db)

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.put_own_layer(
            db,
            workspace_id=S.W1.id,
            attachment_id=a2.id,
            user_id=S.UG.id,
            payload=MP(P1),
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert counts(db) == before


# [claude] AMSV-PL-10
@X2120
def test_amsv_pl_10__concurrent_first_save_becomes_an_update(db, S):
    """AMSV-PL-10 — a concurrent first save becomes an update, committed, no error.
    Rules: put_own_layer R3 (manager R5a) [BUG-2120]."""
    layer(db, S.A1, S.UG, P1)
    commit_point(db)

    with race():
        result = svc.put_own_layer(
            db,
            workspace_id=S.W1.id,
            attachment_id=S.A1.id,
            user_id=S.UG.id,
            payload=MP(P2),
        )

    # Then 1
    assert result.payload == MP(P2)
    # Then 2
    db.rollback()
    rows = layers_of(db, S.A1.id)
    assert len(rows) == 1
    assert rows[0].payload == D(P2)
    # Then 3
    evs = events_of(db, S.A1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_updated"


# [claude] AMSV-PL-11
@X2118
def test_amsv_pl_11__saving_stored_payload_again_commits_no_event(db, S):
    """AMSV-PL-11 — saving the stored payload again commits no event.
    Rules: put_own_layer R1 (manager R7a) [BUG-2118]."""
    layer(db, S.A1, S.UG, P1)
    commit_point(db)

    result = svc.put_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.UG.id, payload=MP(P1)
    )

    # Then 1
    assert result.payload == MP(P1)
    # Then 2
    db.rollback()
    assert len(events_of(db, S.A1.id)) == 0


# [claude] AMSV-PL-12
def test_amsv_pl_12__pending_attachment_raises_unavailable_nothing_written(db, S):
    """AMSV-PL-12 — a pending attachment raises unavailable; nothing written, rolled back.
    Rules: put_own_layer R3, TC3."""
    a2 = att(db, S, "draft.png", upload_status="pending")
    link(db, S, a2, "scratch", 1)
    before = commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.put_own_layer(
            db,
            workspace_id=S.W1.id,
            attachment_id=a2.id,
            user_id=S.UG.id,
            payload=MP(P1),
        )
    # Then 2
    assert str(exc.value) == UNAV
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert counts(db) == before


# =========================================================================== #
# AttachmentMarkupService.delete_own_layer
# =========================================================================== #


# [claude] AMSV-DL-01
def test_amsv_dl_01__callers_layer_deleted_and_markup_cleared_committed(db, S):
    """AMSV-DL-01 — the caller's layer is deleted and markup_cleared committed.
    Rules: delete_own_layer R1, TC1."""
    layer(db, S.A1, S.U1, P1)
    layer(db, S.A1, S.UG, P2)
    commit_point(db)

    result = svc.delete_own_layer(
        db,
        workspace_id=S.W1.id,
        attachment_id=S.A1.id,
        user_id=S.UG.id,
        session_id="s-3",
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    rows = layers_of(db, S.A1.id)
    assert len(rows) == 1
    assert rows[0].user_id == S.U1.id
    # Then 3
    evs = events_of(db, S.A1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_cleared"
    assert evs[0].user_id == S.UG.id
    assert evs[0].session_id == "s-3"
    assert evs[0].description == "Cleared marks"


# [claude] AMSV-DL-02
def test_amsv_dl_02__no_own_layer_nothing_deleted_no_event(db, S):
    """AMSV-DL-02 — no own layer: nothing deleted, no event, no error.
    Rules: delete_own_layer R1."""
    layer(db, S.A1, S.U1, P1)
    before = commit_point(db)

    result = svc.delete_own_layer(
        db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.UG.id
    )

    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before
    # Then 3
    db.rollback()
    rows = layers_of(db, S.A1.id)
    assert len(rows) == 1
    assert rows[0].user_id == S.U1.id


# [claude] AMSV-DL-03
def test_amsv_dl_03__unknown_attachment_rolls_back(db, S):
    """AMSV-DL-03 — an unknown attachment raises not found, rolls back and discards pending changes.
    Rules: delete_own_layer R2, TC3."""
    layer(db, S.A1, S.UG, P1)
    before = commit_point(db)
    x_id = pending_x(db, S)

    # Then 1
    with spies(db) as (cm, rb):
        with pytest.raises(AttachmentNotFoundError) as exc:
            svc.delete_own_layer(
                db, workspace_id=S.W1.id, attachment_id=MISSING, user_id=S.UG.id
            )
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert rb.call_count >= 1
    assert cm.called is False
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


# [claude] AMSV-DL-04
def test_amsv_dl_04__failing_commit_keeps_layer_and_writes_no_event(db, S):
    """AMSV-DL-04 — a failing commit keeps the layer and writes no event.
    Rules: delete_own_layer R2, TC4."""
    lay = layer(db, S.A1, S.UG, P1)
    before = commit_point(db)
    l_id = lay.id

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_own_layer(
                db, workspace_id=S.W1.id, attachment_id=S.A1.id, user_id=S.UG.id
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread_layer(db, l_id)
    assert row.payload == D(P1)
    # Then 4
    assert counts(db) == before


# [claude] AMSV-DL-05
@X2115
def test_amsv_dl_05__private_project_refuses_plain_member_layer_kept(db, S):
    """AMSV-DL-05 — a private project's attachment refuses a plain member; the layer is kept.
    Rules: delete_own_layer R1, R2 [BUG-2115]; PR-3, PR-5."""
    p = proj(db, S, "Tender", private=True)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    lay = layer(db, a2, S.UG, P1)
    before = commit_point(db)
    l_id = lay.id

    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        svc.delete_own_layer(
            db, workspace_id=S.W1.id, attachment_id=a2.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == NFA(a2)
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    row = reread_layer(db, l_id)
    assert row.payload == D(P1)
    # Then 5
    assert counts(db) == before


# [claude] AMSV-DL-06
def test_amsv_dl_06__project_member_clears_layer_on_private_project(db, S):
    """AMSV-DL-06 — a project member clears their layer on the private project's attachment.
    Rules: delete_own_layer R1; PR-2, PR-5."""
    p = proj(db, S, "Tender", private=True)
    pmem(db, S, p, S.UG)
    a2 = att(db, S, "site.png")
    link(db, S, a2, "project", p.id)
    layer(db, a2, S.UG, P1)
    commit_point(db)

    result = svc.delete_own_layer(
        db, workspace_id=S.W1.id, attachment_id=a2.id, user_id=S.UG.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert len(layers_of(db, a2.id)) == 0
    # Then 3
    evs = events_of(db, a2.id)
    assert len(evs) == 1
    assert evs[0].event_type == "markup_cleared"


# [claude] AMSV-DL-07
def test_amsv_dl_07__pending_attachment_raises_unavailable_layer_kept(db, S):
    """AMSV-DL-07 — a pending attachment raises unavailable; the layer is kept, rolled back.
    Rules: delete_own_layer R2, TC3."""
    a2 = att(db, S, "draft.png", upload_status="pending")
    link(db, S, a2, "scratch", 1)
    lay = layer(db, a2, S.UG, P1)
    before = commit_point(db)
    l_id = lay.id
    x_id = pending_x(db, S)

    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        svc.delete_own_layer(
            db, workspace_id=S.W1.id, attachment_id=a2.id, user_id=S.UG.id
        )
    # Then 2
    assert str(exc.value) == UNAV
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    row = reread_layer(db, l_id)
    assert row.payload == D(P1)
    # Then 6
    assert counts(db) == before
