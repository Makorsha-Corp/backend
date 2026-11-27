"""Unit tests for app/managers/attachment_manager.py.

Implements tests/unit/managers/attachment_manager.cases.md (revision 2), one test
per case. Real Postgres session (`db` fixture, rolled back after each test).
Patched (spec Overview "Externals to mock", on app.managers.attachment_manager only):
`get_resource`, `destroy_resource`, `generate_upload_signature`,
`build_signed_delivery_url`, `uuid.uuid4`, `time.time`, and the `settings`
attributes; `app.dao.attachment.utcnow` where a card names the dao clock.
Nothing reaches the network: the cards marked "real gus" / "real bsu" sign locally.
"""
import inspect
import json
import logging
import os
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

import app.managers.attachment_manager as mod
from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.managers.attachment_manager import (
    ENTITY_TYPE_FOLDER_LABELS,
    AttachmentLimitError,
    AttachmentNotFoundError,
    attachment_manager,
)
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.attachment_link import AttachmentLink
from app.models.attachment_markup import AttachmentMarkup
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.invoice_event import InvoiceEvent
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_activity_event import ProjectComponentActivityEvent
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.sales_order import SalesOrder
from app.models.sales_order_event import SalesOrderEvent
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_event import TransferOrderEvent
from app.models.work_order import WorkOrder
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.attachment import AttachmentSignRequest
from app.utils.attachment_allowlist import (
    MAX_FILE_SIZE_BYTES,
    AttachmentConfirmError,
    AttachmentValidationError,
    normalize_upload_request,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

AM = attachment_manager
MISSING = 999999999
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001
TOKEN = "0123456789abcdef0123456789abcdef"
BIG = MAX_FILE_SIZE_BYTES
LOGGER = "app.managers.attachment_manager"
RES = {
    "resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000,
    "secure_url": "https://res.example/s.jpg", "url": "http://res.example/u.jpg",
    "width": 800, "height": 600, "asset_id": "a" * 32, "etag": "e" * 32,
}


def XID(k):
    """Id that no sequence hands out, the same across tables (shared conventions)."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# xfail markers (strict; reason = bug id and title)
X1870 = pytest.mark.xfail(strict=True, reason="BUG-1870: attachments ignore a private project's visibility (sign path)")
X1950 = pytest.mark.xfail(strict=True, reason="BUG-1950: attachments ignore a help ticket's visibility (sign path)")
X2090 = pytest.mark.xfail(strict=True, reason="BUG-2090: sign accepts an unknown, deleted or other-workspace parent")
X2091 = pytest.mark.xfail(strict=True, reason="BUG-2091: actions by attachment id ignore who may open its record")
X2092 = pytest.mark.xfail(strict=True, reason="BUG-2092: confirm never checks the real file size")
X2093 = pytest.mark.xfail(strict=True, reason="BUG-2093: a confirm after a failed try never writes 'Attached'")
X2094 = pytest.mark.xfail(strict=True, reason="BUG-2094: confirm reads the attachment without a row lock (HR-10)")
X2096 = pytest.mark.xfail(strict=True, reason="BUG-2096: 'Cloudinary not configured' at confirm marks the upload failed")
X2097 = pytest.mark.xfail(strict=True, reason="BUG-2097: deleting an already deleted attachment deletes it again")
X2098 = pytest.mark.xfail(strict=True, reason="BUG-2098: deleting a never-ready upload writes 'Removed'")
X2099 = pytest.mark.xfail(strict=True, reason="BUG-2099: deleting a pending or failed upload leaves its Cloudinary file")
X2100 = pytest.mark.xfail(strict=True, reason="BUG-2100: a failed Cloudinary delete is swallowed with no log")
X2101 = pytest.mark.xfail(strict=True, reason="BUG-2101: derive_urls raises when only the API key is missing")
X2102 = pytest.mark.xfail(strict=True, reason="BUG-2102: the sign request's note has no length limit")


# --------------------------------------------------------------------------- #
# Conventions -> Settings (every test) and Externals (every test)
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def cl_settings(monkeypatch):
    s = mod.settings
    monkeypatch.setattr(s, "CLOUDINARY_UPLOAD_ENV", "development")
    monkeypatch.setattr(s, "ENVIRONMENT", "development")
    monkeypatch.setattr(s, "CLOUDINARY_CLOUD_NAME", "demo-cloud")
    monkeypatch.setattr(s, "CLOUDINARY_API_KEY", "123456")
    monkeypatch.setattr(s, "CLOUDINARY_API_SECRET", "s3cret")
    monkeypatch.setattr(s, "MAX_ATTACHMENTS_PER_ENTITY", 25)
    return s


def setting(monkeypatch, name, value):
    """Given line "settings: NAME value"."""
    monkeypatch.setattr(mod.settings, name, value)


_ARGN = ["public_id", "resource_type", "delivery_type", "version"]


def echo(*a, **k):
    """bsu side effect "echo": the URL carries the arguments it was built with.

    The cards read a URL as a dict of its arguments. A plain dict cannot pass the
    `str | None` fields of AttachmentDerivedUrls, so the dict is carried as a JSON
    string and read back with `args_of`."""
    return "echo:" + json.dumps(dict(zip(_ARGN, a), **k), sort_keys=True)


def args_of(url):
    """The arguments a URL from `echo` was built with (u["fmt"], u.get("flags"), ...)."""
    assert isinstance(url, str) and url.startswith("echo:"), url
    return json.loads(url[len("echo:"):])


@pytest.fixture(autouse=True)
def cl():
    """gr / dr / gus / bsu patched on the module under test."""
    patchers = {
        "gr": patch.object(mod, "get_resource", return_value=dict(RES)),
        "dr": patch.object(mod, "destroy_resource", return_value={"result": "ok"}),
        "gus": patch.object(mod, "generate_upload_signature", return_value="sig-x"),
        "bsu": patch.object(mod, "build_signed_delivery_url", side_effect=echo),
    }
    ns = SimpleNamespace(_p=patchers, _real=set())
    for k, p in patchers.items():
        setattr(ns, k, p.start())
    yield ns
    for k, p in patchers.items():
        if k not in ns._real:
            p.stop()


def real(cl, name):
    """Given line "real bsu" / "real gus": that function is not patched in this test."""
    cl._p[name].stop()
    cl._real.add(name)
    setattr(cl, name, None)


def called(cl):
    """cl_untouched reads `.called` of each Cloudinary mock."""
    return {k: getattr(cl, k).called for k in ("gr", "dr", "bsu", "gus")}


UNTOUCHED = {"gr": False, "dr": False, "bsu": False, "gus": False}


@pytest.fixture
def fixed_uuid():
    with patch("app.managers.attachment_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN)) as m:
        yield m


@pytest.fixture
def fixed_time():
    with patch("app.managers.attachment_manager.time.time", return_value=1767225600.9) as m:
        yield m


def call_uid(fn, *args, user_id, **kw):
    """Adds user_id= only when fn already has that parameter (shared conventions)."""
    if "user_id" in inspect.signature(fn).parameters:
        return fn(*args, user_id=user_id, **kw)
    return fn(*args, **kw)


def pg(db, U, **kw):
    """Conventions "pg(U, **kw)"."""
    return call_uid(AM.get_pdf_page_image, db, user_id=U.id, **kw)


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (built in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


def member(db, S, U, role, status="active", ws=None):
    ws = ws or S.W1
    return _add(db, WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status))


def removed(db, S, U, role):
    """removed(U, role) = member(U, role, status="inactive") with left_at T0."""
    m = member(db, S, U, role, status="inactive")
    m.left_at = T0
    db.flush()
    return m


def set_owner(db, W, U):
    W.owner_user_id = U.id
    db.flush()


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db, name="Ana Rahman")
    s.U2 = make_profile(db, name="Bilal Khan")
    s.UG = make_profile(db, name="Mia Khan")
    s.UA = make_profile(db, name="Sam Admin", is_platform_admin=True)
    member(db, s, s.U1, "ground-team")
    member(db, s, s.U2, "owner")
    member(db, s, s.UG, "ground-team")
    s.F0 = _add(db, Factory(workspace_id=s.W0.id, name="Factory Zero", abbreviation="F0"))
    s.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Factory One", abbreviation="F1"))
    s.F9 = _add(db, Factory(workspace_id=s.W2.id, name="Factory Nine", abbreviation="F9"))
    s._deps = {}
    s._fill = 0
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _ws(S, where):
    return {"W0": S.W0, "W1": S.W1, "W2": S.W2}[where]


def _factory(S, where):
    return {"W0": S.F0, "W1": S.F1, "W2": S.F9}[where]


def _deps(db, S, where):
    """Real status / account / work-order-type rows of the parent's workspace."""
    if where not in S._deps:
        ws = _ws(S, where)
        S._deps[where] = SimpleNamespace(
            status=_add(db, Status(workspace_id=ws.id, name="Draft", comment="Stage")),
            account=_add(db, Account(workspace_id=ws.id, name="Acme")),
            wot=_add(db, WorkOrderType(workspace_id=ws.id, name="Repair")),
        )
    return S._deps[where]


def parent(db, S, kind, label, where="W1", deleted=False, **over):
    """parent(type, "L"); `where` = "of W0" / "of W2"; `over` = the columns after "but"."""
    ws, f = _ws(S, where), _factory(S, where)
    d = _deps(db, S, where)
    if kind == "purchase_order":
        fields = {"po_number": label, "destination_type": "storage", "destination_id": f.id, "current_status_id": d.status.id, "created_by": S.U1.id}
        model = PurchaseOrder
    elif kind == "sales_order":
        fields = {"sales_order_number": label, "account_id": d.account.id, "factory_id": f.id, "current_status_id": d.status.id, "created_by": S.U1.id}
        model = SalesOrder
    elif kind == "expense_order":
        fields = {"expense_number": label, "expense_category": "other", "created_by": S.U1.id}
        model = ExpenseOrder
    elif kind == "transfer_order":
        fields = {"transfer_number": label, "source_location_type": "storage", "source_location_id": f.id, "destination_location_type": "storage", "destination_location_id": f.id, "current_status_id": d.status.id, "created_by": S.U1.id}
        model = TransferOrder
    elif kind == "work_order":
        fields = {"work_order_number": label, "work_order_type_id": d.wot.id, "title": "Fix press", "factory_id": f.id}
        model = WorkOrder
        if deleted:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=S.U1.id)
    elif kind == "account_invoice":
        fields = {"invoice_number": label, "account_id": d.account.id, "invoice_type": "payable", "invoice_amount": Decimal("100.00"), "invoice_date": date(2026, 3, 1)}
        model = AccountInvoice
    else:  # pragma: no cover - helper misuse
        raise AssertionError(kind)
    fields["workspace_id"] = ws.id
    fields.update(over)
    return _add(db, model(**fields))


def mach(db, S, name, deleted=False, **over):
    fields = {"workspace_id": S.W1.id, "factory_id": S.F1.id, "name": name}
    if deleted:
        fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Machine(**fields))


def item(db, S, name, sku, **over):
    fields = {"workspace_id": S.W1.id, "name": name, "name_normalized": name.lower(), "unit": "pcs", "sku": sku}
    fields.update(over)
    return _add(db, Item(**fields))


def proj(db, S, name, private=False, deleted=False, **over):
    fields = {"workspace_id": S.W1.id, "factory_id": S.F1.id, "name": name, "description": "Main", "created_by": S.U1.id}
    if private:
        fields["visibility"] = "invited_only"
    if deleted:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Project(**fields))


def comp(db, P, name, **over):
    return _add(db, ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name=name, **over))


def pmem(db, S, P, U):
    return _add(db, ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=S.U1.id))


def ticket(db, S, number, **over):
    fields = {"workspace_id": S.W1.id, "ticket_number": number, "title": "Printer jam", "description": "It jams", "created_by": S.U1.id}
    fields.update(over)
    return _add(db, HelpTicket(**fields))


def att(db, S, pid, ready=False, pdf=False, gone=False, **over):
    """att("pid"); `ready`, `pdf`, `gone` as Conventions; `over` = the columns after "but"."""
    fields = {"workspace_id": S.W1.id, "file_name": "photo.jpg", "mime_type": "image/jpeg", "file_size": 1000, "uploaded_by": S.U1.id, "upload_status": "pending", "public_id": pid, "resource_type": "image", "delivery_type": "authenticated", "note": "Front"}
    if ready:
        fields.update(upload_status="ready", format="jpg", version=1700000000)
    if pdf:
        fields.update(file_name="plan.pdf", mime_type="application/pdf", format="pdf")
    if gone:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=S.U1.id)
    fields.update(over)
    return _add(db, Attachment(**fields))


def link(db, S, A, etype, P, **over):
    """link(A, "type", P); P may be a number."""
    fields = {"workspace_id": A.workspace_id, "attachment_id": A.id, "entity_type": etype, "entity_id": P if isinstance(P, int) else P.id, "linked_by": S.U1.id}
    fields.update(over)
    return _add(db, AttachmentLink(**fields))


_KIND = {
    PurchaseOrder: "purchase_order", SalesOrder: "sales_order", ExpenseOrder: "expense_order",
    TransferOrder: "transfer_order", WorkOrder: "work_order", Project: "project",
    ProjectComponent: "project_component", Machine: "machine", Item: "item",
    AccountInvoice: "account_invoice", HelpTicket: "support_ticket",
}


def fill(db, S, P, n, status):
    """fill(P, n, "status"). Public ids run on across calls of one test (fill-0, fill-1, ...)
    so two fills in one test do not reuse an id."""
    for _ in range(n):
        i = S._fill
        S._fill += 1
        a = att(db, S, f"fill-{i}", upload_status=status)
        link(db, S, a, _KIND[type(P)], P)


def REQ(etype, eid, **over):
    fields = {"entity_type": etype, "entity_id": eid, "file_name": "plan.pdf", "mime_type": "application/pdf", "file_size": 1000, "note": "Site plan"}
    fields.update(over)
    return AttachmentSignRequest(**fields)


def NORM(r):
    return AM.normalize_upload_request(r)


def ET(etype):
    return REQ(etype, 1).entity_type


def create(db, S, R, user, pid="dev/new-1", folder="Dev/F"):
    """The When of most C cards (W1, NORM(R), stored id "dev/new-1", folder "Dev/F")."""
    return AM.create_pending_attachment(db, workspace_id=S.W1.id, user=user, payload=R, normalized=NORM(R),
                                        stored_public_id=pid, asset_folder=folder)


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #

def _columns(model):
    return [c.key for c in sa_inspect(model).mapper.column_attrs]


def snap(db, row):
    """Snapshot for unchanged(X), taken after the last Given line."""
    db.refresh(row)
    return {k: getattr(row, k) for k in _columns(type(row))}


def now_of(db, row):
    """After re-read: every column of X (compare with its snap)."""
    db.expire_all()
    fresh = db.get(type(row), row.id)
    return None if fresh is None else {k: getattr(fresh, k) for k in _columns(type(row))}


def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def ledger_of(db, A):
    db.expire_all()
    return db.execute(select(AttachmentLedger).where(AttachmentLedger.attachment_id == A.id)
                      .order_by(AttachmentLedger.id)).scalars().all()


def links_of(db, A):
    db.expire_all()
    return db.execute(select(AttachmentLink).where(AttachmentLink.attachment_id == A.id)
                      .order_by(AttachmentLink.id)).scalars().all()


_EVENTS = {
    PurchaseOrder: (PurchaseOrderEvent, "purchase_order_id"),
    SalesOrder: (SalesOrderEvent, "sales_order_id"),
    ExpenseOrder: (ExpenseOrderEvent, "expense_order_id"),
    TransferOrder: (TransferOrderEvent, "transfer_order_id"),
    WorkOrder: (WorkOrderEvent, "work_order_id"),
    Project: (ProjectEvent, "project_id"),
    ProjectComponent: (ProjectComponentActivityEvent, "project_component_id"),
    Machine: (MachineActivityEvent, "machine_id"),
    AccountInvoice: (InvoiceEvent, "invoice_id"),
}


def events_of(db, P):
    db.expire_all()
    model, col = _EVENTS[type(P)]
    return db.execute(select(model).where(getattr(model, col) == P.id).order_by(model.id)).scalars().all()


_WRITTEN = (Attachment, AttachmentLink, AttachmentLedger) + tuple(m for m, _ in _EVENTS.values())


def counts(db):
    """"nothing written": row counts of the three attachment tables and the nine activity tables."""
    return tuple(db.execute(select(func.count()).select_from(m)).scalar_one() for m in _WRITTEN)


def session_state(db):
    """`session:` lines: (new, dirty, deleted) right after the call; clean = (False, False, False)."""
    return (bool(db.new), bool(db.dirty), bool(db.deleted))


CLEAN = (False, False, False)


def count_where(db, model, **eq):
    q = select(func.count()).select_from(model)
    for k, v in eq.items():
        q = q.where(getattr(model, k) == v)
    return db.execute(q).scalar_one()


class recorder:
    """Given step "recorder": `stmts` filled by a before_cursor_execute listener during the When only."""

    def __init__(self, db):
        self.conn = db.connection()
        self.stmts = []

    def _rec(self, conn, cursor, statement, params, context, executemany):
        self.stmts.append(statement)

    def __enter__(self):
        event.listen(self.conn, "before_cursor_execute", self._rec)
        return self.stmts

    def __exit__(self, *exc):
        event.remove(self.conn, "before_cursor_execute", self._rec)
        return False


def stored_utc(db, A):
    return db.scalar(text("SELECT deleted_at AT TIME ZONE 'UTC' FROM attachments WHERE id = :i"), {"i": A.id})


@pytest.fixture
def warnings(caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER)
    return caplog


def warning_records(caplog):
    return [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]


# =========================================================================== #
# normalize_upload_request
# =========================================================================== #

def test_atcm_nu_01__valid_request_gives_allowlist_result():
    """ATCM-NU-01 — a valid request gives exactly the allowlist's result.
    Rules: normalize_upload_request R1."""
    r = AttachmentSignRequest(entity_type="purchase_order", entity_id=5, file_name="  Site Plan.PDF ",
                              mime_type="application/pdf", file_size=2048)
    result = AM.normalize_upload_request(r)
    # Then 1
    assert result == normalize_upload_request(r)
    # Then 2
    assert result.file_name == "Site Plan.PDF"
    assert result.resource_type == "image"


def test_atcm_nu_02__invalid_request_raises_allowlist_error():
    """ATCM-NU-02 — an invalid request raises the allowlist's error unchanged.
    Rules: normalize_upload_request R1."""
    r = AttachmentSignRequest(entity_type="purchase_order", entity_id=5, file_name="plan.pdf",
                              mime_type="application/pdf", file_size=10485761)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        AM.normalize_upload_request(r)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."


# =========================================================================== #
# assert_entity_attachment_capacity
# =========================================================================== #

def cap(db, S, eid, etype="purchase_order"):
    return AM.assert_entity_attachment_capacity(db, workspace_id=S.W1.id, entity_type=ET(etype), entity_id=eid)


def test_atcm_cp_01__24_live_pass(db, S):
    """ATCM-CP-01 — 24 live attachments pass, nothing written.
    Rules: assert_entity_attachment_capacity R1, R2."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 12, "pending")
    fill(db, S, PO1, 12, "ready")
    before = counts(db)
    result = cap(db, S, PO1.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before


def test_atcm_cp_02__25_live_refused(db, S):
    """ATCM-CP-02 — 25 live attachments are refused with the maximum in the message.
    Rules: assert_entity_attachment_capacity R1, R3."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 13, "pending")
    fill(db, S, PO1, 12, "ready")
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        cap(db, S, PO1.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."
    # Then 3
    assert state == CLEAN


def test_atcm_cp_03__failed_not_counted(db, S):
    """ATCM-CP-03 — failed attachments are not counted.
    Rules: assert_entity_attachment_capacity R1 [BUG-1434]."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 24, "ready")
    fill(db, S, PO1, 3, "failed")
    result = cap(db, S, PO1.id)
    # Then 1
    assert result is None


def test_atcm_cp_04__deleted_not_counted(db, S):
    """ATCM-CP-04 — deleted attachments are not counted.
    Rules: assert_entity_attachment_capacity R1."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 24, "ready")
    A9 = att(db, S, "gone-1", ready=True, gone=True)
    link(db, S, A9, "purchase_order", PO1)
    result = cap(db, S, PO1.id)
    # Then 1
    assert result is None


def test_atcm_cp_05__maximum_zero_refuses_empty(db, S, monkeypatch):
    """ATCM-CP-05 — the maximum is read from settings at each call; 0 refuses an empty record.
    Rules: assert_entity_attachment_capacity R4, R3."""
    setting(monkeypatch, "MAX_ATTACHMENTS_PER_ENTITY", 0)
    PO1 = parent(db, S, "purchase_order", "PO-1")
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        cap(db, S, PO1.id)
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 0 attachments."


def test_atcm_cp_06__maximum_three_two_pass(db, S, monkeypatch):
    """ATCM-CP-06 — a maximum of 3: 2 pass.
    Rules: assert_entity_attachment_capacity R4, R2."""
    setting(monkeypatch, "MAX_ATTACHMENTS_PER_ENTITY", 3)
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 2, "pending")
    result = cap(db, S, PO1.id)
    # Then 1
    assert result is None


def test_atcm_cp_07__same_id_other_type_not_counted(db, S):
    """ATCM-CP-07 — the same entity_id under another type does not count.
    Rules: assert_entity_attachment_capacity R5."""
    PO1 = parent(db, S, "purchase_order", "PO-1", id=XID(1))
    M1 = mach(db, S, "Lathe", id=XID(1))
    fill(db, S, PO1, 24, "ready")
    fill(db, S, M1, 5, "ready")
    result = cap(db, S, XID(1))
    # Then 1
    assert result is None


def test_atcm_cp_08__w0_w2_links_not_counted(db, S):
    """ATCM-CP-08 — links of W0 and W2 to the same type and id do not count.
    Rules: assert_entity_attachment_capacity R5."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    for pid in ("w0-1", "w0-2", "w0-3"):
        a = att(db, S, pid, workspace_id=S.W0.id)
        link(db, S, a, "purchase_order", PO1)
    fill(db, S, PO1, 24, "ready")
    for pid in ("w2-1", "w2-2", "w2-3"):
        a = att(db, S, pid, workspace_id=S.W2.id)
        link(db, S, a, "purchase_order", PO1)
    result = cap(db, S, PO1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# build_public_id / _upload_env / _is_production
# =========================================================================== #

def test_atcm_pi_01__outside_production_env_prefix(fixed_uuid):
    """ATCM-PI-01 — outside production the id is `<env>/ws-<id>/<token>`.
    Rules: build_public_id R1; _upload_env R1."""
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "development/ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_02__production_no_prefix(monkeypatch, fixed_uuid):
    """ATCM-PI-02 — in production there is no environment prefix.
    Rules: build_public_id R1; _upload_env R2."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "production")
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_03__empty_upload_env_falls_back(monkeypatch, fixed_uuid):
    """ATCM-PI-03 — an empty upload environment falls back to ENVIRONMENT.
    Rules: _upload_env R1, R2."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "")
    setting(monkeypatch, "ENVIRONMENT", "production")
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_04__upload_env_wins(monkeypatch, fixed_uuid):
    """ATCM-PI-04 — a non-empty upload environment wins over ENVIRONMENT.
    Rules: _upload_env R1."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "staging")
    setting(monkeypatch, "ENVIRONMENT", "production")
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "staging/ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_05__capital_production_not_production(monkeypatch, fixed_uuid):
    """ATCM-PI-05 — "Production" with a capital is not production.
    Rules: _upload_env R2."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "Production")
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "Production/ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_06__both_empty_leading_slash(monkeypatch, fixed_uuid):
    """ATCM-PI-06 — both settings empty give a leading slash.
    Rules: build_public_id R1."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "")
    setting(monkeypatch, "ENVIRONMENT", "")
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert result == "/ws-7/0123456789abcdef0123456789abcdef"


def test_atcm_pi_07__each_call_new_token():
    """ATCM-PI-07 — each call mints a new 32-character lowercase hex token.
    Rules: build_public_id R2."""
    first = AM.build_public_id(workspace_id=7)
    result = AM.build_public_id(workspace_id=7)
    # Then 1
    assert re.fullmatch(r"development/ws-7/[0-9a-f]{32}", result) is not None
    # Then 2
    assert re.fullmatch(r"development/ws-7/[0-9a-f]{32}", first) is not None
    # Then 3
    assert result != first


# =========================================================================== #
# build_asset_folder
# =========================================================================== #

def test_atcm_af_01__production_folder(monkeypatch):
    """ATCM-AF-01 — production folder is `<workspace>/<type label>/<record label>`.
    Rules: build_asset_folder R1."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "production")
    result = AM.build_asset_folder(workspace_name="Acme", entity_type=ET("account_invoice"), entity_label="INV-9")
    # Then 1
    assert result == "Acme/Invoices/INV-9"


def test_atcm_af_02__other_env_dev_prefix(monkeypatch):
    """ATCM-AF-02 — any other environment gets "Dev/" whatever its name.
    Rules: build_asset_folder R1."""
    setting(monkeypatch, "CLOUDINARY_UPLOAD_ENV", "staging")
    result = AM.build_asset_folder(workspace_name="Acme", entity_type=ET("item"), entity_label="SKU1")
    # Then 1
    assert result == "Dev/Acme/Items/SKU1"


def test_atcm_af_03__names_used_as_given():
    """ATCM-AF-03 — names are used as given: slashes and outer spaces kept.
    Rules: build_asset_folder R2."""
    result = AM.build_asset_folder(workspace_name=" Acme/East ", entity_type=ET("support_ticket"),
                                   entity_label="HT/1 ")
    # Then 1
    assert result == "Dev/ Acme/East /Help Tickets/HT/1 "


def test_atcm_af_04__type_label_table():
    """ATCM-AF-04 — the type-label table holds exactly the twelve labels.
    Rules: build_asset_folder R1."""
    result = {getattr(k, "value", k): v for k, v in ENTITY_TYPE_FOLDER_LABELS.items()}
    # Then 1
    assert result == {
        "purchase_order": "Purchase Orders", "sales_order": "Sales Orders", "expense_order": "Expense Orders",
        "transfer_order": "Transfer Orders", "work_order": "Work Orders", "project": "Projects",
        "project_component": "Project Components", "item": "Items", "machine": "Machines",
        "account_invoice": "Invoices", "support_ticket": "Help Tickets", "scratch": "Scratch",
    }


# =========================================================================== #
# build_display_name
# =========================================================================== #

def test_atcm_dn_01__slashes_control_chars_trim():
    """ATCM-DN-01 — slashes become dashes, control characters go, outer space is trimmed.
    Rules: build_display_name R1."""
    result = AM.build_display_name("  a/b\\c\x01.pdf ")
    # Then 1
    assert result == "a-b-c.pdf"


def test_atcm_dn_02__control_boundaries():
    """ATCM-DN-02 — \\x00, \\x1f and \\x7f are removed; \\x20 inside and other characters stay.
    Rules: build_display_name R1."""
    result = AM.build_display_name("A\x00b\x1fc\x7fd e~.PDF")
    # Then 1
    assert result == "Abcd e~.PDF"


def test_atcm_dn_03__empty_after_cleaning_upload():
    """ATCM-DN-03 — empty after cleaning becomes "upload".
    Rules: build_display_name R2."""
    result = AM.build_display_name("\x01 ")
    # Then 1
    assert result == "upload"


def test_atcm_dn_04__empty_upload_dash_kept():
    """ATCM-DN-04 — "" becomes "upload"; "-" is kept.
    Rules: build_display_name R2."""
    other = AM.build_display_name("/")
    result = AM.build_display_name("")
    # Then 1
    assert result == "upload"
    # Then 2
    assert other == "-"


def test_atcm_dn_05__cut_to_255():
    """ATCM-DN-05 — 256 characters are cut to 255; 255 stay.
    Rules: build_display_name R3."""
    kept = AM.build_display_name("b" * 255)
    result = AM.build_display_name("a" * 256)
    # Then 1
    assert result == "a" * 255
    # Then 2
    assert kept == "b" * 255


def test_atcm_dn_06__trim_before_cut():
    """ATCM-DN-06 — trimming happens before the cut.
    Rules: build_display_name R1, R3."""
    result = AM.build_display_name("   " + "a" * 254 + "z")
    # Then 1
    assert result == "a" * 254 + "z"


# =========================================================================== #
# resolve_entity_label / _fetch_entity_row
# =========================================================================== #

def label(db, S, etype, eid):
    return AM.resolve_entity_label(db, workspace_id=S.W1.id, entity_type=ET(etype), entity_id=eid)


def test_atcm_rl_01__scratch_reads_nothing(db, S):
    """ATCM-RL-01 — scratch gives scratch-<id> and reads nothing.
    Rules: resolve_entity_label R1."""
    with recorder(db) as stmts:
        result = label(db, S, "scratch", 5)
    # Then 1
    assert result == "scratch-5"
    # Then 2
    assert stmts == []


def test_atcm_rl_02__purchase_order_label(db, S):
    """ATCM-RL-02 — purchase order label is po_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    mach(db, S, "Lathe", id=XID(1))
    parent(db, S, "purchase_order", "PO-77", id=XID(1))
    result = label(db, S, "purchase_order", XID(1))
    # Then 1
    assert result == "PO-77"


def test_atcm_rl_03__sales_order_label(db, S):
    """ATCM-RL-03 — sales order label is sales_order_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "purchase_order", "PO-77", id=XID(2))
    parent(db, S, "sales_order", "SO-12", id=XID(2))
    result = label(db, S, "sales_order", XID(2))
    # Then 1
    assert result == "SO-12"


def test_atcm_rl_04__expense_order_label(db, S):
    """ATCM-RL-04 — expense order label is expense_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "sales_order", "SO-12", id=XID(3))
    parent(db, S, "expense_order", "EXP-3", id=XID(3))
    result = label(db, S, "expense_order", XID(3))
    # Then 1
    assert result == "EXP-3"


def test_atcm_rl_05__transfer_order_label(db, S):
    """ATCM-RL-05 — transfer order label is transfer_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "expense_order", "EXP-3", id=XID(4))
    parent(db, S, "transfer_order", "TR-4", id=XID(4))
    result = label(db, S, "transfer_order", XID(4))
    # Then 1
    assert result == "TR-4"


def test_atcm_rl_06__work_order_label(db, S):
    """ATCM-RL-06 — work order label is work_order_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "transfer_order", "TR-4", id=XID(5))
    parent(db, S, "work_order", "WO-5", id=XID(5))
    result = label(db, S, "work_order", XID(5))
    # Then 1
    assert result == "WO-5"


def test_atcm_rl_07__project_label(db, S):
    """ATCM-RL-07 — project label is its name.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "work_order", "WO-5", id=XID(6))
    proj(db, S, "Tower", id=XID(6))
    result = label(db, S, "project", XID(6))
    # Then 1
    assert result == "Tower"


def test_atcm_rl_08__component_label(db, S):
    """ATCM-RL-08 — project component label is its name.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    P1 = proj(db, S, "Tower", id=XID(7))
    comp(db, P1, "Frame", id=XID(7))
    result = label(db, S, "project_component", XID(7))
    # Then 1
    assert result == "Frame"


def test_atcm_rl_09__machine_label(db, S):
    """ATCM-RL-09 — machine label is its name.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    P0 = proj(db, S, "Tower")
    comp(db, P0, "Frame", id=XID(8))
    mach(db, S, "Lathe", id=XID(8))
    result = label(db, S, "machine", XID(8))
    # Then 1
    assert result == "Lathe"


def test_atcm_rl_10__item_label_is_sku(db, S):
    """ATCM-RL-10 — item label is its sku.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R2."""
    mach(db, S, "Lathe", id=XID(9))
    item(db, S, "Bolt", "SKU-9", id=XID(9))
    result = label(db, S, "item", XID(9))
    # Then 1
    assert result == "SKU-9"


def test_atcm_rl_11__invoice_label(db, S):
    """ATCM-RL-11 — invoice label is invoice_number.
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    item(db, S, "Bolt", "SKU-9", id=XID(10))
    parent(db, S, "account_invoice", "INV-10", id=XID(10))
    result = label(db, S, "account_invoice", XID(10))
    # Then 1
    assert result == "INV-10"


def test_atcm_rl_12__ticket_label(db, S):
    """ATCM-RL-12 — help ticket label is ticket_number (help ticket DAO).
    Rules: resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1."""
    parent(db, S, "account_invoice", "INV-10", id=XID(11))
    ticket(db, S, "HT-11", id=XID(11))
    result = label(db, S, "support_ticket", XID(11))
    # Then 1
    assert result == "HT-11"


def test_atcm_rl_13__unknown_id_fallback(db, S):
    """ATCM-RL-13 — an unknown id falls back to <type>-<id>.
    Rules: resolve_entity_label R2."""
    result = label(db, S, "purchase_order", MISSING)
    # Then 1
    assert result == "purchase_order-999999999"


def test_atcm_rl_14__w0_w2_record_not_found(db, S):
    """ATCM-RL-14 — a W0 or W2 record is not found (both sides of W1).
    Rules: resolve_entity_label R2."""
    P0 = parent(db, S, "purchase_order", "PO-ZERO", where="W0")
    P9 = parent(db, S, "purchase_order", "PO-NINE", where="W2")
    low = label(db, S, "purchase_order", P0.id)
    result = label(db, S, "purchase_order", P9.id)
    # Then 1
    assert result == f"purchase_order-{P9.id}"
    # Then 2
    assert low == f"purchase_order-{P0.id}"


def test_atcm_rl_15__deleted_machine_still_found(db, S):
    """ATCM-RL-15 — a soft-deleted machine is still found (raw).
    Rules: resolve_entity_label R2, R4."""
    MD = mach(db, S, "Old Lathe", deleted=True)
    result = label(db, S, "machine", MD.id)
    # Then 1
    assert result == "Old Lathe"


def test_atcm_rl_16__empty_label_falls_back(db, S):
    """ATCM-RL-16 — an empty label falls back.
    Rules: resolve_entity_label R3."""
    I1 = item(db, S, "", "")
    result = label(db, S, "item", I1.id)
    # Then 1
    assert result == f"item-{I1.id}"


def test_atcm_rl_17__private_project_label(db, S):
    """ATCM-RL-17 — a private project the caller cannot open still gives its label.
    Rules: resolve_entity_label R4."""
    P1 = proj(db, S, "Tender 7", private=True)
    result = label(db, S, "project", P1.id)
    # Then 1
    assert result == "Tender 7"


def test_atcm_rl_18__fetch_scratch_none(db, S):
    """ATCM-RL-18 — _fetch_entity_row for scratch is None.
    Rules: _fetch_entity_row R2."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    result = AM._fetch_entity_row(db, workspace_id=S.W1.id, entity_type=ET("scratch"), entity_id=PO1.id)
    # Then 1
    assert result is None


def test_atcm_rl_19__fetch_returns_row(db, S):
    """ATCM-RL-19 — _fetch_entity_row returns the row itself.
    Rules: _fetch_entity_row R1."""
    H1 = ticket(db, S, "HT-1")
    result = AM._fetch_entity_row(db, workspace_id=S.W1.id, entity_type=ET("support_ticket"), entity_id=H1.id)
    # Then 1
    assert result is H1


# =========================================================================== #
# _extract_entity_label / _attachment_event_metadata
# =========================================================================== #

def test_atcm_xl_01__empty_sku_gives_name():
    """ATCM-XL-01 — item with an empty sku gives its name.
    Rules: _extract_entity_label R2."""
    row = SimpleNamespace(sku="", name="Bolt", po_number="PO-7")
    result = AM._extract_entity_label(ET("item"), row)
    # Then 1
    assert result == "Bolt"


def test_atcm_xl_02__none_sku_gives_name():
    """ATCM-XL-02 — item with sku None gives its name.
    Rules: _extract_entity_label R2."""
    row = SimpleNamespace(sku=None, name="Bolt")
    result = AM._extract_entity_label(ET("item"), row)
    # Then 1
    assert result == "Bolt"


def test_atcm_xl_03__scratch_none():
    """ATCM-XL-03 — scratch gives None.
    Rules: _extract_entity_label R3."""
    row = SimpleNamespace(name="Bolt", sku="S")
    result = AM._extract_entity_label(ET("scratch"), row)
    # Then 1
    assert result is None


def test_atcm_em_01__four_keys():
    """ATCM-EM-01 — exactly the four keys with current values.
    Rules: _attachment_event_metadata R1."""
    a = SimpleNamespace(id=41, file_name="plan.pdf", mime_type="application/pdf", file_size=2048, note="x",
                        public_id="p")
    result = AM._attachment_event_metadata(a)
    # Then 1
    assert result == {"attachment_id": 41, "file_name": "plan.pdf", "mime_type": "application/pdf",
                      "file_size": 2048}


# =========================================================================== #
# _append_attachment_ledger
# =========================================================================== #

def test_atcm_lg_01__enum_stored_as_value(db, S):
    """ATCM-LG-01 — an enum type is stored as its value with every column, flushed.
    Rules: _append_attachment_ledger R1, R2."""
    from app.models.enums import AttachmentLedgerTransactionTypeEnum
    A1 = att(db, S, "dev/a1", file_size=2048)
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id,
                                 transaction_type=AttachmentLedgerTransactionTypeEnum.READY,
                                 entity_type="machine", entity_id=55, performed_by=S.U2.id, notes="ok")
    new = bool(db.new)
    # Then 1
    assert not new
    # Then 2
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 3
    row = rows[0]
    assert row.workspace_id == S.W1.id
    assert row.attachment_id == A1.id
    assert row.transaction_type == "ready"
    assert row.entity_type == "machine"
    assert row.entity_id == 55
    # Then 4
    assert row.file_name == "photo.jpg"
    assert row.mime_type == "image/jpeg"
    assert row.file_size == 2048
    assert row.notes == "ok"
    assert row.performed_by == S.U2.id
    assert row.performed_at is not None


def test_atcm_lg_02__string_stored_as_given(db, S):
    """ATCM-LG-02 — a string type is stored as given.
    Rules: _append_attachment_ledger R1."""
    A1 = att(db, S, "dev/a1")
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="failed",
                                 entity_type="item", entity_id=3)
    # Then 1
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 2
    assert rows[0].transaction_type == "failed"
    assert rows[0].notes is None
    assert rows[0].performed_by is None


def test_atcm_lg_03__entity_from_one_w1_link_as_pair(db, S):
    """ATCM-LG-03 — entity missing: taken from one of the W1 links, as a pair.
    Rules: _append_attachment_ledger R3."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", 70, id=XID(2))
    link(db, S, A1, "purchase_order", 60, id=XID(1))
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="pending")
    # Then 1
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 2
    row = rows[0]
    assert (row.entity_type, row.entity_id) in {("purchase_order", 60), ("machine", 70)}


def test_atcm_lg_04__only_type_given_both_replaced(db, S):
    """ATCM-LG-04 — only entity_type given: both are replaced from the link.
    Rules: _append_attachment_ledger R3."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", 70)
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="pending",
                                 entity_type="item")
    # Then 1
    [row] = ledger_of(db, A1)
    assert row.entity_type == "machine"
    assert row.entity_id == 70


def test_atcm_lg_05__only_id_given_both_replaced(db, S):
    """ATCM-LG-05 — only entity_id given: both are replaced from the link.
    Rules: _append_attachment_ledger R3."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", 70)
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="pending",
                                 entity_id=5)
    # Then 1
    [row] = ledger_of(db, A1)
    assert row.entity_type == "machine"
    assert row.entity_id == 70


def test_atcm_lg_06__w0_w2_links_not_used(db, S):
    """ATCM-LG-06 — links filed under W0 and W2 are not used.
    Rules: _append_attachment_ledger R3, R4."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "item", 11, workspace_id=S.W0.id, id=XID(1))
    link(db, S, A1, "item", 12, workspace_id=S.W2.id, id=XID(2))
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="deleted")
    # Then 1
    [row] = ledger_of(db, A1)
    assert row.entity_type is None
    assert row.entity_id is None


def test_atcm_lg_07__no_link_both_null(db, S):
    """ATCM-LG-07 — no link at all: both NULL.
    Rules: _append_attachment_ledger R4."""
    A1 = att(db, S, "dev/a1")
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="deleted")
    # Then 1
    [row] = ledger_of(db, A1)
    assert row.entity_type is None
    assert row.entity_id is None
    assert row.transaction_type == "deleted"


def test_atcm_lg_08__first_link_is_lowest_link_id(db, S):
    """ATCM-LG-08 — entity missing: the first link is the lowest link id, not the first built.
    Rules: _append_attachment_ledger R3 [BUG-1433]."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", 70, id=XID(2))
    link(db, S, A1, "purchase_order", 60, id=XID(1))
    AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="pending")
    # Then 1
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 2
    assert rows[0].entity_type == "purchase_order"
    assert rows[0].entity_id == 60


def test_atcm_lg_09__links_query_is_ordered(db, S):
    """ATCM-LG-09 — the links query of an attachment is ordered.
    Rules: _append_attachment_ledger R3 [BUG-1433]; to_response R1."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", 70)
    with recorder(db) as stmts:
        AM._append_attachment_ledger(db, attachment=A1, workspace_id=S.W1.id, transaction_type="pending")
    # Then 1
    sel = [s for s in stmts if s.lstrip().upper().startswith("SELECT") and "attachment_links" in s]
    assert len(sel) >= 1
    # Then 2
    assert all("ORDER BY" in s.upper() for s in sel)


# =========================================================================== #
# _log_attachment_entity_events
# =========================================================================== #

def log_events(db, S, A, event_type="attachment_added"):
    return AM._log_attachment_entity_events(db, attachment=A, workspace_id=S.W1.id, event_type=event_type,
                                            performed_by=S.U2.id)


def test_atcm_ev_01__added_on_purchase_order(db, S):
    """ATCM-EV-01 — "attachment_added" on a purchase order writes "Attached <file>".
    Rules: _log_attachment_entity_events R1, R2, R3."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    log_events(db, S, A1)
    # Then 1
    evs = events_of(db, PO1)
    assert len(evs) == 1
    # Then 2
    assert evs[0].event_type == "attachment_added"
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id
    # Then 3
    assert evs[0].metadata_json == {"attachment_id": A1.id, "file_name": "photo.jpg", "mime_type": "image/jpeg",
                                    "file_size": 1000}


def test_atcm_ev_02__removed_writes_removed(db, S):
    """ATCM-EV-02 — "attachment_removed" writes "Removed <file>".
    Rules: _log_attachment_entity_events R1."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    log_events(db, S, A1, "attachment_removed")
    # Then 1
    evs = events_of(db, PO1)
    assert len(evs) == 1
    # Then 2
    assert evs[0].event_type == "attachment_removed"
    assert evs[0].description == "Removed photo.jpg"


def test_atcm_ev_03__other_type_writes_removed(db, S):
    """ATCM-EV-03 — any other event type also writes "Removed".
    Rules: _log_attachment_entity_events R1."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    log_events(db, S, A1, "Attachment_Added")
    # Then 1
    evs = events_of(db, PO1)
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Removed photo.jpg"


def _one_entry(db, S, P, etype):
    """Given A1 = att("dev/a1"); link(A1, etype, P); When: attachment_added by U2."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, etype, P)
    log_events(db, S, A1)
    return events_of(db, P)


def test_atcm_ev_04__sales_order(db, S):
    """ATCM-EV-04 — sales order gets one entry.
    Rules: _log_attachment_entity_events R3."""
    S1 = parent(db, S, "sales_order", "SO-1")
    evs = _one_entry(db, S, S1, "sales_order")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_05__expense_order(db, S):
    """ATCM-EV-05 — expense order gets one entry.
    Rules: _log_attachment_entity_events R3."""
    E1 = parent(db, S, "expense_order", "EXP-1")
    evs = _one_entry(db, S, E1, "expense_order")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_06__transfer_order(db, S):
    """ATCM-EV-06 — transfer order gets one entry.
    Rules: _log_attachment_entity_events R3."""
    T1 = parent(db, S, "transfer_order", "TR-1")
    evs = _one_entry(db, S, T1, "transfer_order")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_07__work_order(db, S):
    """ATCM-EV-07 — work order gets one entry.
    Rules: _log_attachment_entity_events R3."""
    WO1 = parent(db, S, "work_order", "WO-1")
    evs = _one_entry(db, S, WO1, "work_order")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_08__project(db, S):
    """ATCM-EV-08 — project gets one entry.
    Rules: _log_attachment_entity_events R3."""
    P1 = proj(db, S, "Tower")
    evs = _one_entry(db, S, P1, "project")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_09__project_component(db, S):
    """ATCM-EV-09 — project component gets one entry on its activity table.
    Rules: _log_attachment_entity_events R3."""
    P1 = proj(db, S, "Tower")
    C1 = comp(db, P1, "Frame")
    evs = _one_entry(db, S, C1, "project_component")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_10__machine(db, S):
    """ATCM-EV-10 — machine gets one entry.
    Rules: _log_attachment_entity_events R3."""
    M1 = mach(db, S, "Lathe")
    evs = _one_entry(db, S, M1, "machine")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_11__invoice_found(db, S):
    """ATCM-EV-11 — an invoice found in the workspace gets one invoice event.
    Rules: _log_attachment_entity_events R4."""
    N1 = parent(db, S, "account_invoice", "INV-1")
    evs = _one_entry(db, S, N1, "account_invoice")
    # Then 1
    assert len(evs) == 1
    # Then 2
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_ev_12__invoice_not_found(db, S):
    """ATCM-EV-12 — an invoice not found (W2's id) writes nothing and raises nothing.
    Rules: _log_attachment_entity_events R4."""
    N9 = parent(db, S, "account_invoice", "INV-9", where="W2")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "account_invoice", N9)
    result = log_events(db, S, A1)
    # Then 1
    assert result is None
    # Then 2
    assert len(events_of(db, N9)) == 0


def test_atcm_ev_13__item_ticket_scratch_nothing(db, S):
    """ATCM-EV-13 — item, ticket and scratch parents get nothing.
    Rules: _log_attachment_entity_events R5."""
    I1 = item(db, S, "Bolt", "SKU-1")
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "item", I1)
    link(db, S, A1, "support_ticket", H1)
    link(db, S, A1, "scratch", 5)
    before = counts(db)
    result = log_events(db, S, A1)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before


def test_atcm_ev_14__one_per_w1_link(db, S):
    """ATCM-EV-14 — one entry per W1 link; W2-filed link ignored.
    Rules: _log_attachment_entity_events R2."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    M1 = mach(db, S, "Lathe")
    PO2 = parent(db, S, "purchase_order", "PO-2")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", M1)
    link(db, S, A1, "purchase_order", PO2, workspace_id=S.W2.id)
    log_events(db, S, A1)
    # Then 1
    assert len(events_of(db, PO1)) == 1
    # Then 2
    assert len(events_of(db, M1)) == 1
    # Then 3
    assert len(events_of(db, PO2)) == 0


def test_atcm_ev_15__no_link_nothing(db, S):
    """ATCM-EV-15 — no link writes nothing.
    Rules: _log_attachment_entity_events R2."""
    A1 = att(db, S, "dev/a1")
    before = counts(db)
    result = log_events(db, S, A1)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before


# =========================================================================== #
# create_pending_attachment
# =========================================================================== #

def test_atcm_c_01__writes_pending_attachment(db, S):
    """ATCM-C-01 — writes one pending attachment with the server's public id.
    Rules: create_pending_attachment R3."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = AttachmentSignRequest(entity_type="purchase_order", entity_id=PO1.id, file_name="  Site Plan.pdf",
                              mime_type="application/pdf", file_size=4096, note="  Site plan ")
    N = NORM(R)
    result = AM.create_pending_attachment(db, workspace_id=S.W1.id, user=S.UG, payload=R, normalized=N,
                                          stored_public_id="development/ws-7/abc",
                                          asset_folder="Dev/Acme/Purchase Orders/PO-1")
    # Then 1
    assert result.id is not None
    assert result.upload_status == "pending"
    # Then 2
    row = reread(db, Attachment, result.id)
    assert row.workspace_id == S.W1.id
    assert row.file_name == "Site Plan.pdf"
    assert row.mime_type == "application/pdf"
    assert row.resource_type == "image"
    assert row.file_size == 4096
    # Then 3
    assert row.uploaded_by == S.UG.id
    assert row.note == "  Site plan "
    assert row.public_id == "development/ws-7/abc"
    assert row.asset_folder == "Dev/Acme/Purchase Orders/PO-1"
    # Then 4
    assert row.delivery_type == "authenticated"
    assert row.upload_status == "pending"
    assert row.storage_provider == "cloudinary"
    assert row.file_url is None
    assert row.is_deleted is False


def test_atcm_c_02__writes_one_link(db, S):
    """ATCM-C-02 — writes one link to the parent.
    Rules: create_pending_attachment R4."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = REQ("purchase_order", PO1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.id is not None
    # Then 2
    links = links_of(db, result)
    assert len(links) == 1
    # Then 3
    assert links[0].workspace_id == S.W1.id
    assert links[0].entity_type == "purchase_order"
    assert links[0].entity_id == PO1.id
    assert links[0].linked_by == S.UG.id


def test_atcm_c_03__writes_pending_ledger_row(db, S):
    """ATCM-C-03 — writes one pending ledger row.
    Rules: create_pending_attachment R5."""
    M1 = mach(db, S, "Lathe")
    R = REQ("machine", M1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.id is not None
    # Then 2
    rows = ledger_of(db, result)
    assert len(rows) == 1
    # Then 3
    row = rows[0]
    assert row.transaction_type == "pending"
    assert row.entity_type == "machine"
    assert row.entity_id == M1.id
    assert row.performed_by == S.UG.id
    assert row.file_name == "plan.pdf"
    assert row.file_size == 1000


def test_atcm_c_04__no_activity_no_cloudinary(db, S, cl):
    """ATCM-C-04 — no activity entry and no Cloudinary call.
    Rules: create_pending_attachment R7; Side effects."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = REQ("purchase_order", PO1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    # Then 2
    assert len(events_of(db, PO1)) == 0
    # Then 3
    assert called(cl) == UNTOUCHED


def test_atcm_c_05__note_none_stored_none(db, S):
    """ATCM-C-05 — a note of None is stored as None.
    Rules: create_pending_attachment R3."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = REQ("purchase_order", PO1.id, note=None)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, Attachment, result.id).note is None


def test_atcm_c_06__full_record_refused(db, S, cl):
    """ATCM-C-06 — a full record is refused before any write.
    Rules: create_pending_attachment R2; PR-4."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 25, "pending")
    R = REQ("purchase_order", PO1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentLimitError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "This record already has the maximum of 25 attachments."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_c_07__24_then_25th_written(db, S):
    """ATCM-C-07 — 24 attachments: the 25th is written.
    Rules: create_pending_attachment R2."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    fill(db, S, PO1, 24, "ready")
    R = REQ("purchase_order", PO1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    # Then 2
    assert count_where(db, AttachmentLink, workspace_id=S.W1.id, entity_type="purchase_order", entity_id=PO1.id) == 25


def test_atcm_c_08__reused_public_id_fails_flush(db, S):
    """ATCM-C-08 — a reused public id in the same workspace fails at the flush.
    Rules: create_pending_attachment R6."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    att(db, S, "dev/dup")
    R = REQ("purchase_order", PO1.id)
    N = NORM(R)
    # Then 1
    with pytest.raises(IntegrityError), db.begin_nested():
        AM.create_pending_attachment(db, workspace_id=S.W1.id, user=S.UG, payload=R, normalized=N,
                                     stored_public_id="dev/dup", asset_folder="Dev/F")
    # Then 2
    assert count_where(db, Attachment, public_id="dev/dup") == 1


def test_atcm_c_09__same_public_id_other_workspaces(db, S):
    """ATCM-C-09 — the same public id in W0 and W2 does not block W1.
    Rules: create_pending_attachment R6."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    att(db, S, "dev/dup", workspace_id=S.W0.id)
    att(db, S, "dev/dup", workspace_id=S.W2.id)
    R = REQ("purchase_order", PO1.id)
    result = create(db, S, R, S.UG, pid="dev/dup")
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_where(db, Attachment, public_id="dev/dup") == 3


def test_atcm_c_10__scratch_any_id(db, S):
    """ATCM-C-10 — scratch passes with any id.
    Rules: create_pending_attachment R1a; PR-1 (Q14)."""
    R = REQ("scratch", MISSING)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    # Then 2
    [lk] = links_of(db, result)
    assert lk.entity_type == "scratch"
    assert lk.entity_id == 999999999


def test_atcm_c_11__live_component_accepted(db, S):
    """ATCM-C-11 — a live component of a live project is accepted.
    Rules: create_pending_attachment R1a; PR-1."""
    P1 = proj(db, S, "Tower")
    C1 = comp(db, P1, "Frame")
    R = REQ("project_component", C1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_12__never_commits(db, S):
    """ATCM-C-12 — never commits.
    Rules: create_pending_attachment Side effects."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = REQ("purchase_order", PO1.id)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        create(db, S, R, S.UG, pid="dev/spy")
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert count_where(db, Attachment, public_id="dev/spy") == 0


@X2102
def test_atcm_c_13__note_501_refused():
    """ATCM-C-13 — a 501-character note is refused by the sign schema.
    Rules: create_pending_attachment R4a [BUG-2102]."""
    # Then 1
    with pytest.raises(ValidationError):
        AttachmentSignRequest(entity_type="purchase_order", entity_id=1, file_name="plan.pdf",
                              mime_type="application/pdf", file_size=1000, note="n" * 501)


def test_atcm_c_14__note_500_kept():
    """ATCM-C-14 — a 500-character note is accepted and kept as typed.
    Rules: create_pending_attachment R4a."""
    result = AttachmentSignRequest(entity_type="purchase_order", entity_id=1, file_name="plan.pdf",
                                   mime_type="application/pdf", file_size=1000, note=" " + "n" * 499)
    # Then 1
    assert result.note == " " + "n" * 499


def test_atcm_c_43__w1_owner_opens_private(db, S):
    """ATCM-C-43 — the W1 owner opens a private project.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    set_owner(db, S.W1, S.UG)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UG.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_44__active_owner_role_opens(db, S):
    """ATCM-C-44 — an active member with role owner opens it.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    result = create(db, S, R, S.U2)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.U2.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_45__active_gtm_opens(db, S):
    """ATCM-C-45 — an active ground-team-manager opens it.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    UX = make_profile(db, name="Gita Rao")
    member(db, S, UX, "ground-team-manager")
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    result = create(db, S, R, UX)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == UX.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_46__creator_opens(db, S):
    """ATCM-C-46 — the creator opens their private project.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    result = create(db, S, R, S.U1)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.U1.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_47__project_member_opens(db, S):
    """ATCM-C-47 — a project member opens it.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.UG)
    R = REQ("project", P1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UG.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_48__project_member_opens_component(db, S):
    """ATCM-C-48 — a project member opens a component of it.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.UG)
    C1 = comp(db, P1, "Frame")
    R = REQ("project_component", C1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UG.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_49__workspace_project_open(db, S):
    """ATCM-C-49 — a workspace-visible project is open to a plain member.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    P1 = proj(db, S, "Tower")
    R = REQ("project", P1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UG.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_55__ticket_creator_may_attach(db, S):
    """ATCM-C-55 — the ticket's creator may attach.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    H1 = ticket(db, S, "HT-1", created_by=S.UG.id)
    R = REQ("support_ticket", H1.id)
    result = create(db, S, R, S.UG)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UG.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_56__owner_role_any_ticket(db, S):
    """ATCM-C-56 — an active member with role owner may attach to any ticket.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    result = create(db, S, R, S.U2)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.U2.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_57__gtm_any_ticket(db, S):
    """ATCM-C-57 — an active ground-team-manager may attach to any ticket.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    UX = make_profile(db, name="Gita Rao")
    member(db, S, UX, "ground-team-manager")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    result = create(db, S, R, UX)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == UX.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_58__platform_admin_may_attach(db, S):
    """ATCM-C-58 — a platform admin with no membership may attach.
    Rules: create_pending_attachment R1b; PR-2, PR-5."""
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    result = create(db, S, R, S.UA)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == S.UA.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_59__non_member_purchase_order(db, S):
    """ATCM-C-59 — a caller with no membership may attach to a purchase order (no membership check here).
    Rules: create_pending_attachment R1b; PR-2 (G3), PR-5."""
    UX = make_profile(db, name="Nia Shah")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    R = REQ("purchase_order", PO1.id)
    result = create(db, S, R, UX)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == UX.id
    # Then 2
    assert len(links_of(db, result)) == 1


def test_atcm_c_60__non_member_creator_private_project(db, S):
    """ATCM-C-60 — a caller with no membership who created a private project may attach to it.
    Rules: create_pending_attachment R1b; PR-2 (G3), PR-5."""
    UX = make_profile(db, name="Nia Shah")
    P1 = proj(db, S, "Tender 7", private=True, created_by=UX.id)
    R = REQ("project", P1.id)
    result = create(db, S, R, UX)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == UX.id
    # Then 2
    assert len(links_of(db, result)) == 1


# =========================================================================== #
# build_sign_response
# =========================================================================== #

def test_atcm_sr_01__every_field_and_signature(db, S, cl, fixed_time):
    """ATCM-SR-01 — returns every field and signs the response's own values.
    Rules: build_sign_response R3."""
    A1 = att(db, S, "dev/a1", resource_type="raw")
    result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/Acme/Items/SKU1",
                                    display_name="plan.pdf")
    # Then 1
    assert result.attachment_id == A1.id
    assert result.cloud_name == "demo-cloud"
    assert result.api_key == "123456"
    assert result.timestamp == 1767225600
    # Then 2
    assert result.public_id == "dev/a1"
    assert result.asset_folder == "Dev/Acme/Items/SKU1"
    assert result.display_name == "plan.pdf"
    assert result.type == "authenticated"
    # Then 3
    assert result.signature == "sig-x"
    assert result.resource_type == "raw"
    assert result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/raw/upload"
    # Then 4
    assert cl.gus.call_count == 1
    assert cl.gus.call_args.args == ()
    assert cl.gus.call_args.kwargs == {"public_id": "dev/a1", "asset_folder": "Dev/Acme/Items/SKU1",
                                       "display_name": "plan.pdf", "timestamp": 1767225600,
                                       "delivery_type": "authenticated"}


def test_atcm_sr_02__empty_resource_type_image(db, S, fixed_time):
    """ATCM-SR-02 — an empty resource type gives image.
    Rules: build_sign_response R3."""
    A1 = att(db, S, "dev/a1", resource_type="")
    result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")
    # Then 1
    assert result.resource_type == "image"
    # Then 2
    assert result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"


def test_atcm_sr_03__empty_cloud_name_raises(db, S, cl, monkeypatch):
    """ATCM-SR-03 — an empty cloud name raises before signing.
    Rules: build_sign_response R1."""
    setting(monkeypatch, "CLOUDINARY_CLOUD_NAME", "")
    A1 = att(db, S, "dev/a1")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert cl.gus.called is False


def test_atcm_sr_04__empty_api_key_raises(db, S, cl, monkeypatch):
    """ATCM-SR-04 — an empty API key raises before signing.
    Rules: build_sign_response R1."""
    setting(monkeypatch, "CLOUDINARY_API_KEY", "")
    A1 = att(db, S, "dev/a1")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")
    # Then 2
    assert str(exc.value) == "Cloudinary cloud name and API key are required."
    # Then 3
    assert cl.gus.called is False


def test_atcm_sr_05__empty_secret_client_error(db, S, cl, monkeypatch):
    """ATCM-SR-05 — an empty secret raises the client's error from the real signer.
    Rules: build_sign_response R2."""
    real(cl, "gus")
    setting(monkeypatch, "CLOUDINARY_API_SECRET", "")
    A1 = att(db, S, "dev/a1")
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")
    # Then 2
    assert str(exc.value) != "Cloudinary cloud name and API key are required."


def test_atcm_sr_06__writes_nothing(db, S):
    """ATCM-SR-06 — writes nothing.
    Rules: build_sign_response R4."""
    A1 = att(db, S, "dev/a1")
    before = counts(db)
    result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")
    state = session_state(db)
    # Then 1
    assert result.attachment_id == A1.id
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before


# =========================================================================== #
# derive_urls
# =========================================================================== #

def none3(u):
    return (u.thumb_url, u.preview_url, u.download_url)


def test_atcm_du_01__pending_no_urls(db, S, cl):
    """ATCM-DU-01 — a pending attachment has no URLs.
    Rules: derive_urls R1."""
    A1 = att(db, S, "dev/a1", format="jpg", version=1700000000)
    result = AM.derive_urls(A1)
    # Then 1
    assert none3(result) == (None, None, None)
    # Then 2
    assert cl.bsu.called is False


def test_atcm_du_02__failed_no_urls(db, S):
    """ATCM-DU-02 — a failed attachment has no URLs.
    Rules: derive_urls R1."""
    A1 = att(db, S, "dev/a1", upload_status="failed", format="jpg", version=1700000000)
    result = AM.derive_urls(A1)
    # Then 1
    assert none3(result) == (None, None, None)


@pytest.mark.parametrize("over", [
    pytest.param({"public_id": None}, id="ATCM-DU-03"),
    pytest.param({"public_id": ""}, id="ATCM-DU-04"),
    pytest.param({"version": 0}, id="ATCM-DU-05"),
    pytest.param({"version": None}, id="ATCM-DU-06"),
    pytest.param({"format": ""}, id="ATCM-DU-07"),
    pytest.param({"format": None}, id="ATCM-DU-08"),
])
def test_atcm_du_03_08__missing_metadata_no_urls(db, S, over):
    """ATCM-DU-03…08 — public_id / version / format empty (None, "", 0) gives no URLs.
    Rules: derive_urls R2."""
    A1 = att(db, S, "dev/a1", ready=True, **over)
    result = AM.derive_urls(A1)
    # Then 1
    assert none3(result) == (None, None, None)


def test_atcm_du_09__empty_cloud_name_no_urls(db, S, cl, monkeypatch):
    """ATCM-DU-09 — an empty cloud name gives no URLs and raises nothing.
    Rules: derive_urls R3."""
    setting(monkeypatch, "CLOUDINARY_CLOUD_NAME", "")
    A1 = att(db, S, "dev/a1", ready=True)
    result = AM.derive_urls(A1)
    # Then 1
    assert none3(result) == (None, None, None)
    # Then 2
    assert cl.bsu.called is False


def test_atcm_du_10__empty_secret_no_urls(db, S, monkeypatch):
    """ATCM-DU-10 — an empty secret gives no URLs.
    Rules: derive_urls R3."""
    setting(monkeypatch, "CLOUDINARY_API_SECRET", "")
    A1 = att(db, S, "dev/a1", ready=True)
    result = AM.derive_urls(A1)
    # Then 1
    assert none3(result) == (None, None, None)


@X2101
def test_atcm_du_11__empty_api_key_no_urls(db, S, cl, monkeypatch):
    """ATCM-DU-11 — an empty API key gives no URLs instead of raising.
    Rules: derive_urls R3 [BUG-2101]."""
    real(cl, "bsu")
    setting(monkeypatch, "CLOUDINARY_API_KEY", "")
    A1 = att(db, S, "dev/a1", ready=True)
    # Then 1
    result = AM.derive_urls(A1)
    assert none3(result) == (None, None, None)


def test_atcm_du_12__ready_image_three_urls(db, S, cl):
    """ATCM-DU-12 — a ready image: thumb, preview and download with their arguments.
    Rules: derive_urls R4, R7, R8."""
    A1 = att(db, S, "dev/a1", ready=True, format="png", version=1700000001)
    result = AM.derive_urls(A1)
    thumb, preview, download = args_of(result.thumb_url), args_of(result.preview_url), args_of(result.download_url)
    # Then 1
    assert thumb["public_id"] == "dev/a1"
    assert thumb["resource_type"] == "image"
    assert thumb["delivery_type"] == "authenticated"
    assert thumb["version"] == 1700000001
    # Then 2
    assert thumb["fmt"] == "png"
    assert thumb["transformation"] == [{"fetch_format": "auto", "quality": "auto", "width": 400, "crop": "limit"}]
    # Then 3
    assert preview["fmt"] == "png"
    assert preview["transformation"] == [{"fetch_format": "auto", "quality": "auto", "width": 1600, "crop": "limit"}]
    # Then 4
    assert download["fmt"] == "png"
    assert download.get("flags") == "attachment"
    assert download.get("transformation") is None
    # Then 5
    assert cl.bsu.call_count == 3


def test_atcm_du_13__empty_types_fall_back(db, S):
    """ATCM-DU-13 — empty resource and delivery types fall back to image / upload.
    Rules: derive_urls R4."""
    A1 = att(db, S, "dev/a1", ready=True, resource_type="", delivery_type="")
    result = AM.derive_urls(A1)
    preview = args_of(result.preview_url)
    # Then 1
    assert preview["resource_type"] == "image"
    assert preview["delivery_type"] == "upload"


def test_atcm_du_14__raw_only_download(db, S, cl):
    """ATCM-DU-14 — a raw file has only a download URL.
    Rules: derive_urls R5."""
    A1 = att(db, S, "dev/a1", ready=True, file_name="sheet.xlsx",
             mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             resource_type="raw", format="xlsx")
    result = AM.derive_urls(A1)
    # Then 1
    assert result.thumb_url is None
    assert result.preview_url is None
    # Then 2
    download = args_of(result.download_url)
    assert download["resource_type"] == "raw"
    assert download["fmt"] == "xlsx"
    assert download.get("flags") == "attachment"
    # Then 3
    assert cl.bsu.call_count == 1


def test_atcm_du_15__pdf_by_mime_page_thumb(db, S):
    """ATCM-DU-15 — a PDF by MIME type gets a page-1 jpg thumbnail.
    Rules: derive_urls R6, R8."""
    A1 = att(db, S, "dev/a1", ready=True, file_name="plan.pdf", mime_type="application/pdf", format="PDF")
    result = AM.derive_urls(A1)
    thumb, preview, download = args_of(result.thumb_url), args_of(result.preview_url), args_of(result.download_url)
    # Then 1
    assert thumb["fmt"] == "jpg"
    assert thumb["transformation"] == [{"page": 1, "fetch_format": "jpg", "quality": "auto", "width": 400,
                                        "crop": "limit"}]
    # Then 2
    assert preview["fmt"] == "PDF"
    assert download["fmt"] == "PDF"
    assert download.get("flags") == "attachment"


def test_atcm_du_16__pdf_by_format(db, S):
    """ATCM-DU-16 — a PDF by format with another MIME type also gets the page thumbnail.
    Rules: derive_urls R6."""
    A1 = att(db, S, "dev/a1", ready=True, mime_type="image/jpeg", format="pdf")
    result = AM.derive_urls(A1)
    thumb = args_of(result.thumb_url)
    # Then 1
    assert thumb["fmt"] == "jpg"
    assert thumb["transformation"][0]["page"] == 1


# =========================================================================== #
# build_pdf_page_image_url
# =========================================================================== #

def test_atcm_pu_01__page_zero_first(db, S, cl):
    """ATCM-PU-01 — page 0 is refused first, even on a pending non-PDF.
    Rules: build_pdf_page_image_url R1."""
    A1 = att(db, S, "dev/a1")
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        AM.build_pdf_page_image_url(A1, page=0)
    # Then 2
    assert str(exc.value) == "Page number must be at least 1."
    # Then 3
    assert cl.bsu.called is False


def test_atcm_pu_02__not_ready_before_not_pdf(db, S):
    """ATCM-PU-02 — not ready is refused before "not a PDF".
    Rules: build_pdf_page_image_url R2."""
    A1 = att(db, S, "dev/a1")
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        AM.build_pdf_page_image_url(A1, page=1)
    # Then 2
    assert str(exc.value) == "Attachment is not ready."


def test_atcm_pu_03__ready_non_pdf_refused(db, S):
    """ATCM-PU-03 — a ready non-PDF is refused.
    Rules: build_pdf_page_image_url R3."""
    A1 = att(db, S, "dev/a1", ready=True, public_id=None)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        AM.build_pdf_page_image_url(A1, page=1)
    # Then 2
    assert str(exc.value) == "Attachment is not a PDF."


def test_atcm_pu_04__pdf_without_public_id(db, S):
    """ATCM-PU-04 — a PDF without public_id is refused.
    Rules: build_pdf_page_image_url R4."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, public_id="", page_count=1)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        AM.build_pdf_page_image_url(A1, page=2)
    # Then 2
    assert str(exc.value) == "Attachment is missing Cloudinary metadata."


def test_atcm_pu_05__pdf_without_version(db, S):
    """ATCM-PU-05 — a PDF without version is refused.
    Rules: build_pdf_page_image_url R4."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, version=None)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        AM.build_pdf_page_image_url(A1, page=1)
    # Then 2
    assert str(exc.value) == "Attachment is missing Cloudinary metadata."


def test_atcm_pu_06__page_past_count(db, S):
    """ATCM-PU-06 — a page past page_count is refused.
    Rules: build_pdf_page_image_url R5."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, page_count=3)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        AM.build_pdf_page_image_url(A1, page=4)
    # Then 2
    assert str(exc.value) == "Page 4 is out of range (document has 3 pages)."


def test_atcm_pu_07__page_equal_count_passes(db, S):
    """ATCM-PU-07 — page == page_count passes.
    Rules: build_pdf_page_image_url R5, R7."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, page_count=3)
    result = AM.build_pdf_page_image_url(A1, page=3)
    # Then 1
    assert args_of(result)["transformation"][0]["page"] == 3


def test_atcm_pu_08__null_count_any_page(db, S):
    """ATCM-PU-08 — page_count NULL lets any page pass.
    Rules: build_pdf_page_image_url R5."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, page_count=None)
    result = AM.build_pdf_page_image_url(A1, page=500)
    # Then 1
    assert args_of(result)["transformation"][0]["page"] == 500


def test_atcm_pu_09__empty_cloud_name(db, S, cl, monkeypatch):
    """ATCM-PU-09 — an empty cloud name raises "not configured".
    Rules: build_pdf_page_image_url R6."""
    setting(monkeypatch, "CLOUDINARY_CLOUD_NAME", "")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        AM.build_pdf_page_image_url(A1, page=1)
    # Then 2
    assert str(exc.value) == "Cloudinary is not configured."
    # Then 3
    assert cl.bsu.called is False


def test_atcm_pu_10__empty_secret(db, S, monkeypatch):
    """ATCM-PU-10 — an empty secret raises "not configured".
    Rules: build_pdf_page_image_url R6."""
    setting(monkeypatch, "CLOUDINARY_API_SECRET", "")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError) as exc:
        AM.build_pdf_page_image_url(A1, page=1)
    # Then 2
    assert str(exc.value) == "Cloudinary is not configured."


def test_atcm_pu_11__empty_api_key_client_error(db, S, cl, monkeypatch):
    """ATCM-PU-11 — an empty API key raises the client's error.
    Rules: build_pdf_page_image_url R6."""
    real(cl, "bsu")
    setting(monkeypatch, "CLOUDINARY_API_KEY", "")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError):
        AM.build_pdf_page_image_url(A1, page=1)


def test_atcm_pu_12__default_width_full_arguments(db, S, cl):
    """ATCM-PU-12 — default width 1600: full arguments with density 200.
    Rules: build_pdf_page_image_url R7."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, resource_type="", delivery_type="")
    result = AM.build_pdf_page_image_url(A1, page=2)
    u = args_of(result)
    # Then 1
    assert u["public_id"] == "dev/a1"
    assert u["resource_type"] == "image"
    assert u["delivery_type"] == "upload"
    assert u["version"] == 1700000000
    assert u["fmt"] == "jpg"
    # Then 2
    assert u["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600,
                                    "crop": "limit", "density": 200}]
    # Then 3
    assert cl.bsu.call_count == 1


def test_atcm_pu_13__width_1200_density(db, S):
    """ATCM-PU-13 — width 1200 has density.
    Rules: build_pdf_page_image_url R7."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    result = AM.build_pdf_page_image_url(A1, page=1, width=1200)
    t = args_of(result)["transformation"][0]
    # Then 1
    assert t["density"] == 200
    assert t["width"] == 1200


def test_atcm_pu_14__width_1199_no_density(db, S):
    """ATCM-PU-14 — width 1199 has no density.
    Rules: build_pdf_page_image_url R7."""
    A1 = att(db, S, "dev/a1", ready=True, mime_type="image/jpeg", format="pdf")
    result = AM.build_pdf_page_image_url(A1, page=1, width=1199)
    t = args_of(result)["transformation"][0]
    # Then 1
    assert "density" not in t
    assert t["width"] == 1199


def test_atcm_pu_15__pdf_by_mime_type_alone(db, S):
    """ATCM-PU-15 — a PDF by MIME type alone (format "jpg") is accepted.
    Rules: build_pdf_page_image_url R3, R7."""
    A1 = att(db, S, "dev/a1", ready=True, file_name="plan.pdf", mime_type="application/pdf", format="jpg",
             page_count=None)
    result = AM.build_pdf_page_image_url(A1, page=1)
    u = args_of(result)
    # Then 1
    assert u["public_id"] == "dev/a1"
    assert u["fmt"] == "jpg"
    # Then 2
    assert u["transformation"][0]["page"] == 1


# =========================================================================== #
# to_response
# =========================================================================== #

def test_atcm_tr_01__copies_fields_lists_exactly_w1_links(db, S):
    """ATCM-TR-01 — copies every field and lists exactly the W1 links.
    Rules: to_response R1, R2."""
    A1 = att(db, S, "dev/a1", ready=True, width=800, height=600, page_count=None,
             file_url="https://res.example/s.jpg")
    link(db, S, A1, "machine", 70, id=XID(2))
    link(db, S, A1, "purchase_order", 60, id=XID(1))
    link(db, S, A1, "item", 80, workspace_id=S.W2.id, id=XID(3))
    result = AM.to_response(db, A1, workspace_id=S.W1.id)
    # Then 1
    assert sorted((lk.entity_type.value, lk.entity_id) for lk in result.links) == [("machine", 70), ("purchase_order", 60)]
    # Then 2
    assert result.id == A1.id
    assert result.file_name == "photo.jpg"
    assert result.mime_type == "image/jpeg"
    assert result.file_size == 1000
    assert result.note == "Front"
    assert result.uploaded_by == S.U1.id
    # Then 3
    assert result.uploaded_at == A1.uploaded_at
    assert getattr(result.upload_status, "value", result.upload_status) == "ready"
    assert result.public_id == "dev/a1"
    assert result.format == "jpg"
    assert result.version == 1700000000
    # Then 4
    assert result.width == 800
    assert result.height == 600
    assert result.page_count is None
    assert result.file_url == "https://res.example/s.jpg"
    # Then 5
    assert args_of(result.urls.preview_url)["public_id"] == "dev/a1"


def test_atcm_tr_02__none_reads_own_workspace(db, S):
    """ATCM-TR-02 — workspace_id None reads the attachment's own workspace.
    Rules: to_response R1."""
    A9 = att(db, S, "dev/a9", workspace_id=S.W2.id)
    link(db, S, A9, "item", 81, workspace_id=S.W2.id)
    link(db, S, A9, "item", 82, workspace_id=S.W1.id)
    result = AM.to_response(db, A9, workspace_id=None)
    # Then 1
    assert [lk.entity_id for lk in result.links] == [81]


def test_atcm_tr_03__zero_reads_own_workspace(db, S):
    """ATCM-TR-03 — workspace_id 0 reads the attachment's own workspace.
    Rules: to_response R1."""
    A0 = att(db, S, "dev/a0", workspace_id=S.W0.id)
    link(db, S, A0, "item", 81, workspace_id=S.W0.id)
    link(db, S, A0, "item", 82, workspace_id=S.W1.id)
    result = AM.to_response(db, A0, workspace_id=0)
    # Then 1
    assert [lk.entity_id for lk in result.links] == [81]


def test_atcm_tr_04__deleted_mapped(db, S):
    """ATCM-TR-04 — a deleted attachment is mapped like any other.
    Rules: to_response R3."""
    A1 = att(db, S, "dev/a1", ready=True, gone=True)
    link(db, S, A1, "item", 81)
    result = AM.to_response(db, A1, workspace_id=S.W1.id)
    # Then 1
    assert result.id == A1.id
    assert [lk.entity_id for lk in result.links] == [81]


def test_atcm_tr_05__unknown_link_type_raises(db, S):
    """ATCM-TR-05 — an unknown link type raises ValueError.
    Rules: to_response R4."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "Purchase_Order", 81)
    # Then 1
    with pytest.raises(ValueError):
        AM.to_response(db, A1, workspace_id=S.W1.id)


def test_atcm_tr_06__pending_urls_none(db, S):
    """ATCM-TR-06 — a pending attachment's urls are all None.
    Rules: to_response R2."""
    A1 = att(db, S, "dev/a1")
    result = AM.to_response(db, A1, workspace_id=S.W1.id)
    # Then 1
    assert none3(result.urls) == (None, None, None)
    assert result.links == []


# =========================================================================== #
# get_pdf_page_image — pass cards (through pg)
# =========================================================================== #

def test_atcm_tr_07__w1_links_in_link_id_order(db, S):
    """ATCM-TR-07 — W1 links are listed in link id order, not build order.
    Rules: to_response R1 [BUG-1433]."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "machine", 70, id=XID(2))
    link(db, S, A1, "purchase_order", 60, id=XID(1))
    result = AM.to_response(db, A1, workspace_id=S.W1.id)
    # Then 1
    assert [(lk.entity_type.value, lk.entity_id) for lk in result.links] == [("purchase_order", 60), ("machine", 70)]


def test_atcm_pg_01__page_url_page_count(db, S):
    """ATCM-PG-01 — returns the page URL, the page and the page count; writes nothing.
    Rules: get_pdf_page_image R3; PR-5 (via pg)."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, page_count=3)
    link(db, S, A1, "purchase_order", PO1)
    before = counts(db)
    result = pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=2)
    state = session_state(db)
    # Then 1
    assert result["page"] == 2
    assert result["page_count"] == 3
    # Then 2
    u = args_of(result["url"])
    assert u["public_id"] == "dev/a1"
    assert u["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600,
                                    "crop": "limit", "density": 200}]
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before


def test_atcm_pg_02__width_passed_on(db, S):
    """ATCM-PG-02 — the width is passed on.
    Rules: get_pdf_page_image R3; PR-5 (via pg)."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "scratch", 5)
    result = pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=1, width=800)
    t = args_of(result["url"])["transformation"][0]
    # Then 1
    assert t["width"] == 800
    assert "density" not in t


def test_atcm_pg_03__unknown_id(db, S, cl):
    """ATCM-PG-03 — an unknown id is not found.
    Rules: get_pdf_page_image R1; PR-5 (via pg)."""
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        pg(db, S.UG, attachment_id=MISSING, workspace_id=S.W1.id, page=1)
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert called(cl) == UNTOUCHED


def test_atcm_pg_04__deleted_not_found(db, S, cl):
    """ATCM-PG-04 — a deleted attachment is not found.
    Rules: get_pdf_page_image R1; PR-5 (via pg)."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, gone=True)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert called(cl) == UNTOUCHED


def test_atcm_pg_05__w0_not_found(db, S, cl):
    """ATCM-PG-05 — a W0 attachment is not found from W1.
    Rules: get_pdf_page_image R1; PR-5 (via pg)."""
    A0 = att(db, S, "dev/a0", ready=True, pdf=True, workspace_id=S.W0.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        pg(db, S.UG, attachment_id=A0.id, workspace_id=S.W1.id, page=1)
    # Then 2
    assert str(exc.value) == f"Attachment {A0.id} not found."
    # Then 3
    assert called(cl) == UNTOUCHED


def test_atcm_pg_06__w2_not_found(db, S, cl):
    """ATCM-PG-06 — a W2 attachment is not found from W1.
    Rules: get_pdf_page_image R1; PR-5 (via pg)."""
    A9 = att(db, S, "dev/a9", ready=True, pdf=True, workspace_id=S.W2.id)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        pg(db, S.UG, attachment_id=A9.id, workspace_id=S.W1.id, page=1)
    # Then 2
    assert str(exc.value) == f"Attachment {A9.id} not found."
    # Then 3
    assert called(cl) == UNTOUCHED


def test_atcm_pg_07__page_error_passes_through(db, S):
    """ATCM-PG-07 — a page error of the URL builder passes through.
    Rules: get_pdf_page_image R3; PR-5 (via pg)."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True, page_count=3)
    link(db, S, A1, "scratch", 5)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=4)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "Page 4 is out of range (document has 3 pages)."
    # Then 3
    assert state == CLEAN


def test_atcm_pg_33__project_member_allowed(db, S, cl):
    """ATCM-PG-33 — allowed: a project member reaches its private project's attachment.
    Rules: get_pdf_page_image R2; PR-3, PR-5 (via pg)."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    result = pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


def test_atcm_pg_34__platform_admin_ticket_allowed(db, S, cl):
    """ATCM-PG-34 — allowed: a platform admin reaches a ticket's attachment.
    Rules: get_pdf_page_image R2; PR-3, PR-5 (via pg)."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "support_ticket", H1)
    result = pg(db, S.UA, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


def test_atcm_pg_35__scratch_open(db, S, cl):
    """ATCM-PG-35 — allowed: a scratch attachment is open to a plain member.
    Rules: get_pdf_page_image R2; PR-3, PR-5 (via pg)."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "scratch", 5)
    result = pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


def test_atcm_pg_36__non_member_purchase_order(db, S, cl):
    """ATCM-PG-36 — allowed: a caller with no membership reaches a purchase order's attachment.
    Rules: get_pdf_page_image R2; PR-2 (G3), PR-3, PR-5 (via pg)."""
    UX = make_profile(db, name="Nia Shah")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", PO1)
    result = pg(db, UX, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


def test_atcm_pg_41__w2_link_ignored(db, S, cl):
    """ATCM-PG-41 — allowed: a link filed under W2 to a missing purchase order is ignored.
    Rules: get_pdf_page_image R2; PR-3 (only W1 links count), PR-5 (via pg)."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "scratch", 5)
    link(db, S, A1, "purchase_order", MISSING, workspace_id=S.W2.id)
    result = pg(db, S.UG, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


# =========================================================================== #
# confirm_attachment
# =========================================================================== #

def confirm(db, S, A, by):
    return AM.confirm_attachment(db, attachment_id=A.id, workspace_id=S.W1.id, performed_by=by)


def status_of(x):
    return getattr(x.upload_status, "value", x.upload_status)


def test_atcm_cf_01__unknown_id(db, S, cl):
    """ATCM-CF-01 — an unknown id is not found, nothing asked of Cloudinary.
    Rules: confirm_attachment R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=MISSING, workspace_id=S.W1.id, performed_by=S.U2.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "Attachment 999999999 not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@pytest.mark.parametrize("where", [
    pytest.param("gone", id="ATCM-CF-02"),
    pytest.param("W0", id="ATCM-CF-03"),
    pytest.param("W2", id="ATCM-CF-04"),
])
def test_atcm_cf_02_04__deleted_or_other_workspace(db, S, cl, where):
    """ATCM-CF-02…04 — a deleted attachment, a W0 or a W2 attachment is not found from W1.
    Rules: confirm_attachment R1."""
    if where == "gone":
        A1 = att(db, S, "dev/a1", gone=True)
    else:
        A1 = att(db, S, "dev/a" + where[1], workspace_id=getattr(S, where).id)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_cf_05__ready_returned_unchanged(db, S, cl):
    """ATCM-CF-05 — an attachment already ready is returned unchanged.
    Rules: confirm_attachment R2."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    snap_a1 = snap(db, A1)
    result = confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert state == CLEAN
    # Then 3
    assert now_of(db, A1) == snap_a1
    # Then 4
    assert len(ledger_of(db, A1)) == 0
    # Then 5
    assert len(events_of(db, PO1)) == 0
    # Then 6
    assert called(cl) == UNTOUCHED


def test_atcm_cf_06__no_public_id_refused(db, S, cl):
    """ATCM-CF-06 — no public_id is refused before Cloudinary.
    Rules: confirm_attachment R3."""
    A1 = att(db, S, "dev/a1", public_id=None)
    link(db, S, A1, "scratch", 5)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "Attachment has no public_id."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_cf_07__empty_public_id_refused(db, S, cl):
    """ATCM-CF-07 — public_id "" is refused the same way.
    Rules: confirm_attachment R3."""
    A1 = att(db, S, "dev/a1", public_id="")
    link(db, S, A1, "scratch", 5)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "Attachment has no public_id."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert cl.gr.called is False


def test_atcm_cf_08__lookup_error_marks_failed(db, S, cl):
    """ATCM-CF-08 — a lookup error marks the upload failed, records it, then raises.
    Rules: confirm_attachment R4, R9."""
    cl.gr.side_effect = RuntimeError("timeout")
    A1 = att(db, S, "dev/a1")
    M1 = mach(db, S, "Press")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    link(db, S, A1, "machine", M1, id=XID(2))
    link(db, S, A1, "purchase_order", PO1, id=XID(1))
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    new, dirty = bool(db.new), bool(db.dirty)
    # Then 2
    assert str(exc.value) == "Cloudinary verification failed: timeout"
    # Then 3
    assert not new
    assert not dirty
    # Then 4
    row = reread(db, Attachment, A1.id)
    assert row.upload_status == "failed"
    assert row.file_url is None
    # Then 5
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].transaction_type == "failed"
    assert rows[0].notes == "timeout"
    assert rows[0].performed_by == S.U2.id
    # Then 7
    assert (rows[0].entity_type, rows[0].entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}


def test_atcm_cf_09__no_actor_uploader_recorded(db, S, cl):
    """ATCM-CF-09 — with no actor, the uploader is recorded.
    Rules: confirm_attachment Inputs, R4; PR-5."""
    cl.gr.side_effect = RuntimeError("timeout")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    # Then 1
    with pytest.raises(AttachmentConfirmError):
        confirm(db, S, A1, None)
    # Then 2
    [row] = ledger_of(db, A1)
    assert row.performed_by == S.U1.id


def test_atcm_cf_10__asks_stored_id_and_types(db, S, cl):
    """ATCM-CF-10 — the lookup asks only about the stored id, with the stored types.
    Rules: confirm_attachment R4 (OQ-11)."""
    A1 = att(db, S, "dev/a1", file_name="notes.txt", mime_type="text/plain", resource_type="raw",
             delivery_type="upload")
    link(db, S, A1, "scratch", 5)
    cl.gr.return_value = {"resource_type": "raw", "format": "txt", "bytes": 10, "version": 1,
                          "secure_url": "https://res.example/n.txt"}
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert cl.gr.call_count == 1
    assert cl.gr.call_args.args == ()
    assert cl.gr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "raw", "delivery_type": "upload"}


def test_atcm_cf_11__empty_types_asked_as_defaults(db, S, cl):
    """ATCM-CF-11 — empty stored types are asked as image / authenticated.
    Rules: confirm_attachment R4."""
    A1 = att(db, S, "dev/a1", resource_type="", delivery_type="")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert cl.gr.call_count == 1
    assert cl.gr.call_args.args == ()
    assert cl.gr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "image",
                                      "delivery_type": "authenticated"}


@X2096
def test_atcm_cf_12__not_configured_passes_through(db, S, cl):
    """ATCM-CF-12 — "not configured" passes through and nothing is written.
    Rules: confirm_attachment R4a [BUG-2096]."""
    cl.gr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(CloudinaryNotConfiguredError):
        confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 2
    assert state == CLEAN
    # Then 3
    assert now_of(db, A1) == snap_a1
    # Then 4
    assert len(ledger_of(db, A1)) == 0


def test_atcm_cf_13__format_not_allowed_failed(db, S, cl):
    """ATCM-CF-13 — a format the file name does not allow marks it failed.
    Rules: confirm_attachment R5, R9."""
    cl.gr.return_value = {**RES, "format": "png"}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    msg = "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    # Then 2
    assert str(exc.value) == msg
    # Then 3
    row = reread(db, Attachment, A1.id)
    assert row.upload_status == "failed"
    assert row.format is None
    # Then 4
    [lg] = ledger_of(db, A1)
    assert lg.transaction_type == "failed"
    assert lg.notes == msg
    assert lg.performed_by == S.U2.id


def test_atcm_cf_14__wrong_resource_type_failed(db, S, cl):
    """ATCM-CF-14 — a wrong resource type marks it failed.
    Rules: confirm_attachment R5."""
    cl.gr.return_value = {**RES, "resource_type": "raw"}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    # Then 2
    assert str(exc.value) == "Cloudinary resource_type 'raw' does not match .jpg (expected 'image')."
    # Then 3
    assert reread(db, Attachment, A1.id).upload_status == "failed"
    # Then 4
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_15__extension_not_allowed_passes(db, S):
    """ATCM-CF-15 — an extension no longer allowed passes its error and writes nothing.
    Rules: confirm_attachment R5 (BUG-124)."""
    A1 = att(db, S, "dev/a1", file_name="tool.exe")
    link(db, S, A1, "scratch", 5)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentValidationError) as exc:
        confirm(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "Unsupported file extension: .exe"
    # Then 3
    assert state == CLEAN
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert len(ledger_of(db, A1)) == 0


def test_atcm_cf_16__success_stores_values(db, S, cl):
    """ATCM-CF-16 — success stores Cloudinary's values and marks it ready.
    Rules: confirm_attachment R6."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    assert status_of(result) == "ready"
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.upload_status == "ready"
    assert row.file_url == "https://res.example/s.jpg"
    assert row.file_size == 1234
    assert row.format == "jpg"
    assert row.version == 1700000000
    # Then 3
    assert row.width == 800
    assert row.height == 600
    assert row.page_count is None
    assert row.asset_id == "a" * 32
    assert row.etag == "e" * 32
    assert row.mime_type == "image/jpeg"
    # Then 4
    assert cl.dr.called is False


def test_atcm_cf_17__plain_url_without_secure(db, S, cl):
    """ATCM-CF-17 — without secure_url the plain url is stored.
    Rules: confirm_attachment R6."""
    cl.gr.return_value = {k: v for k, v in RES.items() if k != "secure_url"}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert reread(db, Attachment, A1.id).file_url == "http://res.example/u.jpg"


def test_atcm_cf_18__bytes_zero_keeps_size(db, S, cl):
    """ATCM-CF-18 — bytes 0 keeps the declared size.
    Rules: confirm_attachment R6."""
    cl.gr.return_value = {**RES, "bytes": 0}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert reread(db, Attachment, A1.id).file_size == 1000


def test_atcm_cf_19__missing_values_overwrite_none(db, S, cl):
    """ATCM-CF-19 — values Cloudinary does not send overwrite with None.
    Rules: confirm_attachment R6."""
    cl.gr.return_value = {"resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000,
                          "secure_url": "https://res.example/s.jpg"}
    A1 = att(db, S, "dev/a1", width=10, height=20, page_count=5, asset_id="old-asset", etag="old-etag")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.width is None
    assert row.height is None
    assert row.page_count is None
    assert row.asset_id is None
    assert row.etag is None


def test_atcm_cf_20__image_pdf_sets_mime_and_pages(db, S, cl):
    """ATCM-CF-20 — an image resource of format pdf sets the PDF MIME type and page count.
    Rules: confirm_attachment R6."""
    cl.gr.return_value = {**RES, "format": "pdf", "pages": 4}
    A1 = att(db, S, "dev/a1", file_name="plan.pdf", mime_type="application/octet-stream")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.mime_type == "application/pdf"
    assert row.page_count == 4
    assert row.format == "pdf"


def test_atcm_cf_21__raw_keeps_mime(db, S, cl):
    """ATCM-CF-21 — a raw file keeps its MIME type.
    Rules: confirm_attachment R6."""
    cl.gr.return_value = {"resource_type": "raw", "format": "txt", "bytes": 10, "version": 1,
                          "secure_url": "https://res.example/n.txt"}
    A1 = att(db, S, "dev/a1", file_name="notes.txt", mime_type="text/plain", resource_type="raw")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.mime_type == "text/plain"
    assert row.format == "txt"
    assert row.file_size == 10


def test_atcm_cf_22__exactly_max_accepted(db, S, cl):
    """ATCM-CF-22 — exactly 10 485 760 bytes is accepted.
    Rules: confirm_attachment R6a."""
    cl.gr.return_value = {**RES, "bytes": 10485760}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert reread(db, Attachment, A1.id).file_size == 10485760
    # Then 3
    assert cl.dr.called is False


@X2092
def test_atcm_cf_23__over_max_refused(db, S, cl):
    """ATCM-CF-23 — 10 485 761 bytes: file deleted, failed, refused.
    Rules: confirm_attachment R6a [BUG-2092]."""
    cl.gr.return_value = {**RES, "bytes": 10485761}
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    # Then 1
    with pytest.raises(AttachmentConfirmError) as exc:
        confirm(db, S, A1, S.U2.id)
    # Then 2
    assert str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."
    # Then 3
    assert cl.dr.call_count == 1
    assert cl.dr.call_args.kwargs["public_id"] == "dev/a1"
    # Then 4
    assert reread(db, Attachment, A1.id).upload_status == "failed"
    # Then 5
    [lg] = ledger_of(db, A1)
    assert lg.transaction_type == "failed"
    assert lg.notes == "File too large (10485761 bytes). Maximum is 10485760 bytes."


def test_atcm_cf_24__ready_ledger_row(db, S):
    """ATCM-CF-24 — one ready ledger row with the actor and one of the links.
    Rules: confirm_attachment R7."""
    M1 = mach(db, S, "Lathe")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", M1, id=XID(2))
    link(db, S, A1, "purchase_order", PO1, id=XID(1))
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].transaction_type == "ready"
    assert rows[0].performed_by == S.U2.id
    assert rows[0].file_size == 1234
    # Then 4
    assert (rows[0].entity_type, rows[0].entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}


def test_atcm_cf_25__pending_every_parent_attached(db, S):
    """ATCM-CF-25 — from pending, every parent gets "Attached …" by the actor.
    Rules: confirm_attachment R8."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", M1)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    [e1] = events_of(db, PO1)
    assert e1.event_type == "attachment_added"
    assert e1.description == "Attached photo.jpg"
    assert e1.performed_by == S.U2.id
    # Then 3
    [e2] = events_of(db, M1)
    assert e2.description == "Attached photo.jpg"
    assert e2.performed_by == S.U2.id


def test_atcm_cf_26__no_actor_events_name_uploader(db, S):
    """ATCM-CF-26 — with no actor the events name the uploader.
    Rules: confirm_attachment Inputs, R7, R8."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    result = confirm(db, S, A1, None)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    [e1] = events_of(db, PO1)
    assert e1.performed_by == S.U1.id
    # Then 3
    [lg] = ledger_of(db, A1)
    assert lg.performed_by == S.U1.id


def test_atcm_cf_27__failed_confirmed_again_ready(db, S):
    """ATCM-CF-27 — a failed upload confirmed again becomes ready with a ready ledger row.
    Rules: confirm_attachment R6, R7."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", upload_status="failed")
    link(db, S, A1, "purchase_order", PO1)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    [lg] = ledger_of(db, A1)
    assert lg.transaction_type == "ready"


@X2093
def test_atcm_cf_28__failed_confirmed_again_attached(db, S):
    """ATCM-CF-28 — a failed upload confirmed again writes "Attached …".
    Rules: confirm_attachment R8 [BUG-2093]."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", upload_status="failed")
    link(db, S, A1, "purchase_order", PO1)
    result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    evs = events_of(db, PO1)
    assert len(evs) == 1
    assert evs[0].description == "Attached photo.jpg"
    assert evs[0].performed_by == S.U2.id


def test_atcm_cf_29__other_member_may_confirm(db, S):
    """ATCM-CF-29 — a member other than the uploader may confirm.
    Rules: confirm_attachment R11."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    [lg] = ledger_of(db, A1)
    assert lg.performed_by == S.UG.id
    # Then 3
    assert reread(db, Attachment, A1.id).uploaded_by == S.U1.id


def test_atcm_cf_30__never_commits(db, S):
    """ATCM-CF-30 — never commits.
    Rules: confirm_attachment Side effects."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        confirm(db, S, A1, S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, Attachment, A1.id).upload_status == "pending"


@X2094
def test_atcm_cf_31__read_with_row_lock(db, S):
    """ATCM-CF-31 — the attachment is read with a row lock.
    Rules: confirm_attachment R10 [BUG-2094]."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    with recorder(db) as stmts:
        result = confirm(db, S, A1, S.U2.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    locked = [s for s in stmts if s.lstrip().upper().startswith("SELECT") and "attachments" in s and "FOR UPDATE" in s]
    assert locked != []


def test_atcm_cf_80__project_member_allowed(db, S):
    """ATCM-CF-80 — allowed: a project member reaches its private project's attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_81__platform_admin_ticket(db, S):
    """ATCM-CF-81 — allowed: a platform admin reaches a ticket's attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    result = confirm(db, S, A1, S.UA.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_82__scratch_open(db, S):
    """ATCM-CF-82 — allowed: a scratch attachment is open to a plain member.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_83__creator_allowed(db, S):
    """ATCM-CF-83 — allowed: the creator reaches their private project's attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    result = confirm(db, S, A1, S.U1.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_84__w1_owner_allowed(db, S):
    """ATCM-CF-84 — allowed: the W1 owner reaches a private project's attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    set_owner(db, S.W1, S.UG)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_85__gtm_any_ticket(db, S):
    """ATCM-CF-85 — allowed: an active ground-team-manager reaches any ticket's attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    UX = make_profile(db, name="Gita Rao")
    member(db, S, UX, "ground-team-manager")
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    result = confirm(db, S, A1, UX.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_86__ticket_creator(db, S):
    """ATCM-CF-86 — allowed: the ticket's creator reaches its attachment.
    Rules: confirm_attachment R1a; PR-3, PR-5."""
    H1 = ticket(db, S, "HT-1", created_by=S.UG.id)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_87__non_member_purchase_order(db, S):
    """ATCM-CF-87 — allowed: a caller with no membership reaches a purchase order's attachment.
    Rules: confirm_attachment R1a; PR-2 (G3), PR-3, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    result = confirm(db, S, A1, UX.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_88__none_actor_creator_uploader(db, S):
    """ATCM-CF-88 — allowed: with performed_by None the uploader is the caller: the creator-uploader reaches the
    private project.
    Rules: confirm_attachment R1a; Inputs, PR-5 (G7), PR-3."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    result = confirm(db, S, A1, None)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_90__caller_is_performed_by(db, S):
    """ATCM-CF-90 — allowed: the caller is performed_by, not the uploader: the creator confirms a plain member's
    upload.
    Rules: confirm_attachment R1a; Inputs, PR-5 (G7), PR-3."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", uploaded_by=S.UG.id)
    link(db, S, A1, "project", P1)
    result = confirm(db, S, A1, S.U1.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


def test_atcm_cf_97__w2_link_ignored(db, S):
    """ATCM-CF-97 — allowed: a link filed under W2 to a missing purchase order is ignored.
    Rules: confirm_attachment R1a; PR-3 (only W1 links count), PR-5."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    link(db, S, A1, "purchase_order", MISSING, workspace_id=S.W2.id)
    result = confirm(db, S, A1, S.UG.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


# =========================================================================== #
# delete_attachment
# =========================================================================== #

def delete(db, S, A, by):
    return AM.delete_attachment(db, attachment_id=A.id, workspace_id=S.W1.id, deleted_by=by)


def test_atcm_d_01__unknown_id_none(db, S, cl):
    """ATCM-D-01 — an unknown id gives None, nothing written, no Cloudinary call.
    Rules: delete_attachment R1."""
    before = counts(db)
    result = AM.delete_attachment(db, attachment_id=MISSING, workspace_id=S.W1.id, deleted_by=S.U2.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert called(cl) == UNTOUCHED


@pytest.mark.parametrize("where", [pytest.param("W0", id="ATCM-D-02"), pytest.param("W2", id="ATCM-D-03")])
def test_atcm_d_02_03__other_workspace_none(db, S, cl, where):
    """ATCM-D-02, ATCM-D-03 — a W0 / W2 attachment gives None.
    Rules: delete_attachment R1."""
    A = att(db, S, "dev/a" + where[1], ready=True, workspace_id=getattr(S, where).id)
    snap_a = snap(db, A)
    result = delete(db, S, A, S.U2.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert now_of(db, A) == snap_a
    # Then 4
    assert called(cl) == UNTOUCHED


@X2097
def test_atcm_d_04__already_deleted_missing(db, S, cl):
    """ATCM-D-04 — an attachment already deleted answers as missing.
    Rules: delete_attachment R1 [BUG-2097]."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True, gone=True)
    link(db, S, A1, "purchase_order", PO1)
    snap_a1 = snap(db, A1)
    result = delete(db, S, A1, S.U2.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert now_of(db, A1) == snap_a1
    # Then 4
    assert len(ledger_of(db, A1)) == 0
    # Then 5
    assert len(events_of(db, PO1)) == 0
    # Then 6
    assert called(cl) == UNTOUCHED


def test_atcm_d_05__member_soft_deletes_ready(db, S):
    """ATCM-D-05 — a member soft-deletes a ready attachment; links and markup stay.
    Rules: delete_attachment R2, R8; Facts (deleted_at clock)."""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    with patch("app.dao.attachment.utcnow", return_value=NOW):
        PO1 = parent(db, S, "purchase_order", "PO-1")
        A1 = att(db, S, "dev/a1", ready=True)
        link(db, S, A1, "purchase_order", PO1)
        _add(db, AttachmentMarkup(workspace_id=S.W1.id, attachment_id=A1.id, user_id=S.U1.id,
                                  payload={"shapes": [1]}))
        result = delete(db, S, A1, S.UG.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id
    # Then 3
    assert stored_utc(db, A1) == NOW
    # Then 4
    assert len(links_of(db, A1)) == 1
    # Then 5
    assert count_where(db, AttachmentMarkup, attachment_id=A1.id) == 1


def test_atcm_d_06__deleted_ledger_row(db, S):
    """ATCM-D-06 — a deleted ledger row with the deleter and one of the links.
    Rules: delete_attachment R3."""
    M1 = mach(db, S, "Lathe")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "machine", M1, id=XID(2))
    link(db, S, A1, "purchase_order", PO1, id=XID(1))
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    rows = ledger_of(db, A1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].transaction_type == "deleted"
    assert rows[0].performed_by == S.U2.id
    # Then 4
    assert (rows[0].entity_type, rows[0].entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}


def test_atcm_d_07__pending_ledger_row(db, S):
    """ATCM-D-07 — a pending attachment also gets the deleted ledger row.
    Rules: delete_attachment R3."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    [lg] = ledger_of(db, A1)
    assert lg.transaction_type == "deleted"
    assert lg.performed_by == S.U2.id


def test_atcm_d_08__failed_ledger_row(db, S):
    """ATCM-D-08 — a failed attachment also gets the deleted ledger row.
    Rules: delete_attachment R3."""
    A1 = att(db, S, "dev/a1", upload_status="failed")
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    [lg] = ledger_of(db, A1)
    assert lg.transaction_type == "deleted"


def test_atcm_d_09__ready_removed_every_parent(db, S):
    """ATCM-D-09 — a ready attachment writes "Removed …" on every parent.
    Rules: delete_attachment R4."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    M1 = mach(db, S, "Lathe")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", M1)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    [e1] = events_of(db, PO1)
    assert e1.event_type == "attachment_removed"
    assert e1.description == "Removed photo.jpg"
    assert e1.performed_by == S.U2.id
    # Then 3
    [e2] = events_of(db, M1)
    assert e2.description == "Removed photo.jpg"


@X2098
@pytest.mark.parametrize("status", [pytest.param("pending", id="ATCM-D-10"), pytest.param("failed", id="ATCM-D-11")])
def test_atcm_d_10_11__never_ready_no_removed(db, S, status):
    """ATCM-D-10, ATCM-D-11 — a pending / failed attachment writes no "Removed …".
    Rules: delete_attachment R4 [BUG-2098]."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", upload_status=status)
    link(db, S, A1, "purchase_order", PO1)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert len(events_of(db, PO1)) == 0


def test_atcm_d_12__ready_file_deleted_stored_types(db, S, cl):
    """ATCM-D-12 — a ready file is deleted from Cloudinary by its stored id and types.
    Rules: delete_attachment R5 (OQ-11)."""
    A1 = att(db, S, "dev/a1", ready=True, resource_type="raw", delivery_type="upload", file_name="notes.txt",
             mime_type="text/plain", format="txt")
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert cl.dr.call_count == 1
    assert cl.dr.call_args.args == ()
    assert cl.dr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "raw", "delivery_type": "upload"}


def test_atcm_d_13__empty_types_defaults(db, S, cl):
    """ATCM-D-13 — empty stored types are deleted as image / authenticated.
    Rules: delete_attachment R5."""
    A1 = att(db, S, "dev/a1", ready=True, resource_type="", delivery_type="")
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert cl.dr.call_count == 1
    assert cl.dr.call_args.args == ()
    assert cl.dr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "image",
                                      "delivery_type": "authenticated"}


@X2099
@pytest.mark.parametrize("status", [pytest.param("pending", id="ATCM-D-14"), pytest.param("failed", id="ATCM-D-15")])
def test_atcm_d_14_15__never_ready_file_deleted(db, S, cl, status):
    """ATCM-D-14, ATCM-D-15 — a pending / failed file is deleted from Cloudinary too.
    Rules: delete_attachment R6 [BUG-2099]."""
    A1 = att(db, S, "dev/a1", upload_status=status)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert cl.dr.call_count == 1
    assert cl.dr.call_args.kwargs["public_id"] == "dev/a1"


def test_atcm_d_16__no_public_id_no_cloudinary(db, S, cl):
    """ATCM-D-16 — no public_id: nothing is asked of Cloudinary.
    Rules: delete_attachment R5, R6."""
    A1 = att(db, S, "dev/a1", public_id=None)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert cl.dr.called is False


def test_atcm_d_17__cloudinary_error_swallowed(db, S, cl):
    """ATCM-D-17 — a Cloudinary error is swallowed; the delete still happens.
    Rules: delete_attachment R7."""
    cl.dr.side_effect = RuntimeError("boom")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert reread(db, Attachment, A1.id).is_deleted is True
    # Then 3
    assert len(ledger_of(db, A1)) == 1


def test_atcm_d_18__not_configured_swallowed(db, S, cl):
    """ATCM-D-18 — "not configured" from Cloudinary is swallowed too.
    Rules: delete_attachment R7."""
    cl.dr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert reread(db, Attachment, A1.id).is_deleted is True


@X2100
def test_atcm_d_19__failed_delete_logs_warning(db, S, cl, warnings):
    """ATCM-D-19 — a failed Cloudinary delete logs one warning naming the id and the error.
    Rules: delete_attachment R7 [BUG-2100]."""
    cl.dr.side_effect = RuntimeError("boom")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    recs = warning_records(warnings)
    assert len(recs) == 1
    # Then 3
    assert "dev/a1" in recs[0].getMessage()
    assert "boom" in recs[0].getMessage()


def test_atcm_d_20__success_no_warning(db, S, warnings):
    """ATCM-D-20 — a successful delete logs no warning.
    Rules: delete_attachment R7."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.U2.id)
    # Then 1
    assert result.id == A1.id
    # Then 2
    assert len(warning_records(warnings)) == 0


def test_atcm_d_21__never_commits(db, S):
    """ATCM-D-21 — never commits.
    Rules: delete_attachment Side effects."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        delete(db, S, A1, S.U2.id)
        sp.rollback()
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert reread(db, Attachment, A1.id).is_deleted is False


def test_atcm_d_53__project_member_allowed(db, S):
    """ATCM-D-53 — allowed: a project member reaches its private project's attachment.
    Rules: delete_attachment R1a; PR-3, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.UG)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    result = delete(db, S, A1, S.UG.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id


def test_atcm_d_54__platform_admin_ticket(db, S):
    """ATCM-D-54 — allowed: a platform admin reaches a ticket's attachment.
    Rules: delete_attachment R1a; PR-3, PR-5."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "support_ticket", H1)
    result = delete(db, S, A1, S.UA.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UA.id


def test_atcm_d_55__scratch_open(db, S):
    """ATCM-D-55 — allowed: a scratch attachment is open to a plain member.
    Rules: delete_attachment R1a; PR-3, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    result = delete(db, S, A1, S.UG.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id


def test_atcm_d_56__non_member_purchase_order(db, S):
    """ATCM-D-56 — allowed: a caller with no membership reaches a purchase order's attachment.
    Rules: delete_attachment R1a; PR-2 (G3), PR-3, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    PO1 = parent(db, S, "purchase_order", "PO-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    result = delete(db, S, A1, UX.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == UX.id


def test_atcm_d_61__w2_link_ignored(db, S):
    """ATCM-D-61 — allowed: a link filed under W2 to a missing purchase order is ignored.
    Rules: delete_attachment R1a; PR-3 (only W1 links count), PR-5."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5)
    link(db, S, A1, "purchase_order", MISSING, workspace_id=S.W2.id)
    result = delete(db, S, A1, S.UG.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == S.UG.id


# =========================================================================== #
# create_pending_attachment — refusals (PR-1 / PR-2, strict xfail)
# =========================================================================== #


@X2090
def test_atcm_c_21__unknown_po_refused(db, S, cl):
    """ATCM-C-21 — an unknown purchase order id is refused as not found
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    R = REQ("purchase_order", MISSING)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "purchase_order 999999999 not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_22__deleted_machine_refused(db, S, cl):
    """ATCM-C-22 — a soft-deleted machine is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    MD = mach(db, S, "Old Lathe", deleted=True)
    R = REQ("machine", MD.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"machine {MD.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_23__deleted_work_order_refused(db, S, cl):
    """ATCM-C-23 — a soft-deleted work order is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    WD = parent(db, S, "work_order", "WO-9", deleted=True)
    R = REQ("work_order", WD.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"work_order {WD.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_24__deleted_project_refused(db, S, cl):
    """ATCM-C-24 — a soft-deleted project is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    PD = proj(db, S, "Old Tower", deleted=True)
    R = REQ("project", PD.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {PD.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_25__component_of_deleted_project_refused(db, S, cl):
    """ATCM-C-25 — a component of a deleted project is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    PD = proj(db, S, "Old Tower", deleted=True)
    C1 = comp(db, PD, "Frame")
    R = REQ("project_component", C1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project_component {C1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_26__w0_po_refused(db, S, cl):
    """ATCM-C-26 — a W0 purchase order (workspace before W1) is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    P0 = parent(db, S, "purchase_order", "PO-ZERO", where="W0")
    R = REQ("purchase_order", P0.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"purchase_order {P0.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_27__w2_po_refused(db, S, cl):
    """ATCM-C-27 — a W2 purchase order (workspace after W1) is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    P9 = parent(db, S, "purchase_order", "PO-NINE", where="W2")
    R = REQ("purchase_order", P9.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"purchase_order {P9.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_28__machine_id_not_a_po(db, S, cl):
    """ATCM-C-28 — a W1 machine holding the asked id does not make a purchase order exist
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    mach(db, S, "Lathe", id=XID(1))
    R = REQ("purchase_order", XID(1))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"purchase_order {XID(1)} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_29__w2_ticket_refused(db, S, cl):
    """ATCM-C-29 — a W2 help ticket is refused
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    H9 = ticket(db, S, "HT-9", workspace_id=S.W2.id)
    R = REQ("support_ticket", H9.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H9.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_30__w2_machine_refused(db, S, cl):
    """ATCM-C-30 — a W2 machine is refused next to a live W1 machine
    Rules: create_pending_attachment R1a [BUG-2090]; PR-1, PR-4."""
    mach(db, S, "Lathe")
    M9 = mach(db, S, "Far Press", workspace_id=S.W2.id, factory_id=S.F9.id)
    R = REQ("machine", M9.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"machine {M9.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2090
def test_atcm_c_31__unknown_before_capacity(db, S, cl, monkeypatch):
    """ATCM-C-31 — an unknown parent is refused as not found before the capacity check
    Rules: create_pending_attachment R1a [BUG-2090], R2; PR-4."""
    setting(monkeypatch, "MAX_ATTACHMENTS_PER_ENTITY", 0)
    R = REQ("purchase_order", MISSING)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == "purchase_order 999999999 not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_32__plain_member_private_project(db, S, cl):
    """ATCM-C-32 — a plain member is refused a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_33__plain_member_private_component(db, S, cl):
    """ATCM-C-33 — a plain member is refused a component of a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    R = REQ("project_component", C1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project_component {C1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_34__suspended_owner_refused(db, S, cl):
    """ATCM-C-34 — a suspended member with role owner is refused
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", status="suspended")
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_35__owning_w0_not_open(db, S, cl):
    """ATCM-C-35 — owning W0 does not open a private project of W1
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    set_owner(db, S.W0, S.UG)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_36__owning_w2_not_open(db, S, cl):
    """ATCM-C-36 — owning W2 does not open a private project of W1
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    set_owner(db, S.W2, S.UG)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_37__privileged_w0_w2_not_open(db, S, cl):
    """ATCM-C-37 — privileged only in W0 and W2 does not open it
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    member(db, S, S.UG, "owner", ws=S.W0)
    member(db, S, S.UG, "ground-team-manager", ws=S.W2)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_38__other_project_membership_not_open(db, S, cl):
    """ATCM-C-38 — membership of other private projects (lower and higher id) does not open this one
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    PA = proj(db, S, "Alpha", private=True)
    P1 = proj(db, S, "Tender 7", private=True)
    PB = proj(db, S, "Beta", private=True)
    pmem(db, S, PA, S.UG)
    pmem(db, S, PB, S.UG)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_39__others_membership_not_open(db, S, cl):
    """ATCM-C-39 — other users' membership of this project does not open it
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    pmem(db, S, P1, S.U1)
    UZ = make_profile(db, name="Zed Ali")
    pmem(db, S, P1, UZ)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_40__creator_of_others_not_open(db, S, cl):
    """ATCM-C-40 — having created other projects (lower and higher id) does not open this one
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    proj(db, S, "Alpha", created_by=S.UG.id)
    P1 = proj(db, S, "Tender 7", private=True)
    proj(db, S, "Beta", created_by=S.UG.id)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_41__no_creator_closed(db, S, cl):
    """ATCM-C-41 — a private project with no creator is closed to a plain member
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True, created_by=None)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_42__hidden_before_capacity(db, S, cl):
    """ATCM-C-42 — the hidden-project refusal comes before the capacity check
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    fill(db, S, P1, 25, "ready")
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_50__plain_member_other_ticket(db, S, cl):
    """ATCM-C-50 — a plain member is refused another member's ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_51__creator_of_other_tickets(db, S, cl):
    """ATCM-C-51 — creating other tickets (lower and higher id) does not open this one
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    ticket(db, S, "HT-A", created_by=S.UG.id)
    H1 = ticket(db, S, "HT-1")
    ticket(db, S, "HT-B", created_by=S.UG.id)
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_52__ticket_no_creator_closed(db, S, cl):
    """ATCM-C-52 — a ticket with no creator is closed to a plain member
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1", created_by=None)
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UG)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_53__role_capital_owner_not_view_all(db, S, cl):
    """ATCM-C-53 — a membership role "Owner" with a capital is not a view-all role
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "Owner")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_54__role_part_word_not_view_all(db, S, cl):
    """ATCM-C-54 — a membership role "ground-team-manage" (part of the word) is not a view-all role
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manage")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_61__non_member_judged_private_project(db, S, cl):
    """ATCM-C-61 — a caller with no membership is still judged on a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_62__non_member_judged_ticket(db, S, cl):
    """ATCM-C-62 — a caller with no membership is still judged on another member's ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_63__owner_only_w0_private_project(db, S, cl):
    """ATCM-C-63 — privileged (owner) only in W0 does not open a private project of W1
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_64__gtm_only_w2_private_project(db, S, cl):
    """ATCM-C-64 — privileged (ground-team-manager) only in W2 does not open a private project of W1
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_65__removed_owner_private_project(db, S, cl):
    """ATCM-C-65 — a removed (inactive) owner is refused a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "owner")
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_66__suspended_gtm_private_project(db, S, cl):
    """ATCM-C-66 — a suspended ground-team-manager is refused a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", status="suspended")
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_67__suspended_owner_ticket(db, S, cl):
    """ATCM-C-67 — a suspended owner is refused another member's ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", status="suspended")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_68__removed_gtm_ticket(db, S, cl):
    """ATCM-C-68 — a removed (inactive) ground-team-manager is refused another member's ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "ground-team-manager")
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_69__owner_only_w0_ticket(db, S, cl):
    """ATCM-C-69 — owner only in W0 does not open a W1 ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1950
def test_atcm_c_70__gtm_only_w2_ticket(db, S, cl):
    """ATCM-C-70 — ground-team-manager only in W2 does not open a W1 ticket
    Rules: create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, UX)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"support_ticket {H1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_21__po_missing(db, S, cl):
    """ATCM-PG-21 — refused: its purchase order does not exist
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", MISSING)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_22__machine_deleted(db, S, cl):
    """ATCM-PG-22 — refused: its machine is soft-deleted
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "machine", MD)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_23__wo_deleted(db, S, cl):
    """ATCM-PG-23 — refused: its work order is soft-deleted
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    WD = parent(db, S, "work_order", "WO-9", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "work_order", WD)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_24__comp_project_deleted(db, S, cl):
    """ATCM-PG-24 — refused: its component's project is deleted
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    PD = proj(db, S, "Old Tower", deleted=True)
    C1 = comp(db, PD, "Frame")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_25__po_w0(db, S, cl):
    """ATCM-PG-25 — refused: its purchase order belongs to W0
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    P0 = parent(db, S, "purchase_order", "PO-ZERO", where="W0")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", P0)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_26__po_w2(db, S, cl):
    """ATCM-PG-26 — refused: its purchase order belongs to W2
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    P9 = parent(db, S, "purchase_order", "PO-NINE", where="W2")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", P9)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_27__machine_holds_po_id(db, S, cl):
    """ATCM-PG-27 — refused: only a W1 machine holds its purchase-order id
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    mach(db, S, "Lathe", id=XID(1))
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", XID(1))
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_28__one_of_two_deleted(db, S, cl):
    """ATCM-PG-28 — refused: one of its two links is a deleted machine
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", MD)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_29__private_project(db, S, cl):
    """ATCM-PG-29 — refused: its private project is hidden from a plain member
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_30__private_component(db, S, cl):
    """ATCM-PG-30 — refused: its component's private project is hidden
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_31__other_ticket(db, S, cl):
    """ATCM-PG-31 — refused: a ticket of another member is hidden
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_32__one_hidden_of_two(db, S, cl):
    """ATCM-PG-32 — refused: one hidden link among an open one refuses (any link)
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_37__suspended_owner_project(db, S, cl):
    """ATCM-PG-37 — refused: a suspended owner is refused a private project
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", status="suspended")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_38__removed_owner_project(db, S, cl):
    """ATCM-PG-38 — refused: a removed (inactive) owner is refused a private project
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "owner")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_39__owner_w0_project(db, S, cl):
    """ATCM-PG-39 — refused: privileged (owner) only in W0 does not open a private project of W1
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_40__gtm_w2_project(db, S, cl):
    """ATCM-PG-40 — refused: privileged (ground-team-manager) only in W2 does not open a private project of W1
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_42__only_w2_link(db, S, cl):
    """ATCM-PG-42 — refused: its only link is filed under W2 (no W1 link)
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "scratch", 5, workspace_id=S.W2.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_43__no_link(db, S, cl):
    """ATCM-PG-43 — refused: it has no link at all
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_61__po_missing(db, S, cl):
    """ATCM-CF-61 — refused: its purchase order does not exist
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", MISSING)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_62__machine_deleted(db, S, cl):
    """ATCM-CF-62 — refused: its machine is soft-deleted
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "machine", MD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_63__wo_deleted(db, S, cl):
    """ATCM-CF-63 — refused: its work order is soft-deleted
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    WD = parent(db, S, "work_order", "WO-9", deleted=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "work_order", WD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_64__comp_project_deleted(db, S, cl):
    """ATCM-CF-64 — refused: its component's project is deleted
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    PD = proj(db, S, "Old Tower", deleted=True)
    C1 = comp(db, PD, "Frame")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_65__po_w0(db, S, cl):
    """ATCM-CF-65 — refused: its purchase order belongs to W0
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    P0 = parent(db, S, "purchase_order", "PO-ZERO", where="W0")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", P0)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_66__po_w2(db, S, cl):
    """ATCM-CF-66 — refused: its purchase order belongs to W2
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    P9 = parent(db, S, "purchase_order", "PO-NINE", where="W2")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", P9)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_67__machine_holds_po_id(db, S, cl):
    """ATCM-CF-67 — refused: only a W1 machine holds its purchase-order id
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    mach(db, S, "Lathe", id=XID(1))
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", XID(1))
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_68__one_of_two_deleted(db, S, cl):
    """ATCM-CF-68 — refused: one of its two links is a deleted machine
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", MD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_69__private_project(db, S, cl):
    """ATCM-CF-69 — refused: its private project is hidden from a plain member
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_70__private_component(db, S, cl):
    """ATCM-CF-70 — refused: its component's private project is hidden
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_71__other_ticket(db, S, cl):
    """ATCM-CF-71 — refused: a ticket of another member is hidden
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_72__one_hidden_of_two(db, S, cl):
    """ATCM-CF-72 — refused: one hidden link among an open one refuses (any link)
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_73__owning_w0_project(db, S, cl):
    """ATCM-CF-73 — refused: owning W0 does not open its private project
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    set_owner(db, S.W0, S.UG)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_74__privileged_w2_project(db, S, cl):
    """ATCM-CF-74 — refused: privileged only in W2 does not open its private project
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    member(db, S, S.UG, "owner", ws=S.W2)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_75__other_project_membership(db, S, cl):
    """ATCM-CF-75 — refused: membership of other private projects (lower and higher id) does not open it
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    PA = proj(db, S, "Alpha", private=True)
    P1 = proj(db, S, "Tender 7", private=True)
    PB = proj(db, S, "Beta", private=True)
    pmem(db, S, PA, S.UG)
    pmem(db, S, PB, S.UG)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_76__no_creator_project(db, S, cl):
    """ATCM-CF-76 — refused: a private project with no creator is hidden from a plain member
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True, created_by=None)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_77__suspended_owner_project(db, S, cl):
    """ATCM-CF-77 — refused: a suspended owner is refused its private project
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", status="suspended")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_78__creator_of_other_tickets(db, S, cl):
    """ATCM-CF-78 — refused: creating other tickets (lower and higher id) does not open this one
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    ticket(db, S, "HT-A", created_by=S.UG.id)
    H1 = ticket(db, S, "HT-1")
    ticket(db, S, "HT-B", created_by=S.UG.id)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_79__ticket_no_creator(db, S, cl):
    """ATCM-CF-79 — refused: a ticket with no creator is hidden from a plain member
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1", created_by=None)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_89__none_actor_plain_uploader(db, S, cl):
    """ATCM-CF-89 — refused: with performed_by None the uploader is the caller: a plain uploader is refused the private project
    Rules: confirm_attachment R1a [BUG-2091]; Inputs, PR-3, PR-4, PR-5 (G7)."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", uploaded_by=S.UG.id)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=None)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_91__owner_w0_project(db, S, cl):
    """ATCM-CF-91 — refused: privileged (owner) only in W0 does not open a private project of W1
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_92__removed_owner_project(db, S, cl):
    """ATCM-CF-92 — refused: a removed (inactive) owner is refused a private project
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "owner")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_93__suspended_gtm_ticket(db, S, cl):
    """ATCM-CF-93 — refused: a suspended ground-team-manager is refused another member's ticket
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", status="suspended")
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_94__removed_owner_ticket(db, S, cl):
    """ATCM-CF-94 — refused: a removed (inactive) owner is refused another member's ticket
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "owner")
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_95__owner_w0_ticket(db, S, cl):
    """ATCM-CF-95 — refused: owner only in W0 does not open a W1 ticket
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_96__gtm_w2_ticket(db, S, cl):
    """ATCM-CF-96 — refused: ground-team-manager only in W2 does not open a W1 ticket
    Rules: confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_98__only_w2_link(db, S, cl):
    """ATCM-CF-98 — refused: its only link is filed under W2 (no W1 link)
    Rules: confirm_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "scratch", 5, workspace_id=S.W2.id)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_99__no_link(db, S, cl):
    """ATCM-CF-99 — refused: it has no link at all
    Rules: confirm_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1")
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_41__po_missing(db, S, cl):
    """ATCM-D-41 — refused: its purchase order does not exist
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", MISSING)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_42__machine_deleted(db, S, cl):
    """ATCM-D-42 — refused: its machine is soft-deleted
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "machine", MD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_43__wo_deleted(db, S, cl):
    """ATCM-D-43 — refused: its work order is soft-deleted
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    WD = parent(db, S, "work_order", "WO-9", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "work_order", WD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_44__comp_project_deleted(db, S, cl):
    """ATCM-D-44 — refused: its component's project is deleted
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    PD = proj(db, S, "Old Tower", deleted=True)
    C1 = comp(db, PD, "Frame")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_45__po_w0(db, S, cl):
    """ATCM-D-45 — refused: its purchase order belongs to W0
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    P0 = parent(db, S, "purchase_order", "PO-ZERO", where="W0")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", P0)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_46__po_w2(db, S, cl):
    """ATCM-D-46 — refused: its purchase order belongs to W2
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    P9 = parent(db, S, "purchase_order", "PO-NINE", where="W2")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", P9)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_47__machine_holds_po_id(db, S, cl):
    """ATCM-D-47 — refused: only a W1 machine holds its purchase-order id
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    mach(db, S, "Lathe", id=XID(1))
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", XID(1))
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_48__one_of_two_deleted(db, S, cl):
    """ATCM-D-48 — refused: one of its two links is a deleted machine
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    MD = mach(db, S, "Old Lathe", deleted=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "machine", MD)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_49__private_project(db, S, cl):
    """ATCM-D-49 — refused: its private project is hidden from a plain member
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_50__private_component(db, S, cl):
    """ATCM-D-50 — refused: its component's private project is hidden
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_51__other_ticket(db, S, cl):
    """ATCM-D-51 — refused: a ticket of another member is hidden
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_52__one_hidden_of_two(db, S, cl):
    """ATCM-D-52 — refused: one hidden link among an open one refuses (any link)
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    PO1 = parent(db, S, "purchase_order", "PO-1")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "purchase_order", PO1)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_57__suspended_owner_project(db, S, cl):
    """ATCM-D-57 — refused: a suspended owner is refused a private project
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", status="suspended")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=UX.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_58__removed_owner_project(db, S, cl):
    """ATCM-D-58 — refused: a removed (inactive) owner is refused a private project
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    removed(db, S, UX, "owner")
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=UX.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_59__owner_w0_project(db, S, cl):
    """ATCM-D-59 — refused: privileged (owner) only in W0 does not open a private project of W1
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "owner", ws=S.W0)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=UX.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_60__gtm_w2_project(db, S, cl):
    """ATCM-D-60 — refused: privileged (ground-team-manager) only in W2 does not open a private project of W1
    Rules: delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5."""
    UX = make_profile(db, name="Sue Park")
    member(db, S, UX, "ground-team-manager", ws=S.W2)
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=UX.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_62__only_w2_link(db, S, cl):
    """ATCM-D-62 — refused: its only link is filed under W2 (no W1 link)
    Rules: delete_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "scratch", 5, workspace_id=S.W2.id)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_63__no_link(db, S, cl):
    """ATCM-D-63 — refused: it has no link at all
    Rules: delete_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5."""
    A1 = att(db, S, "dev/a1", ready=True)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UG.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


# =========================================================================== #
# Revision 4 — platform admin on private records, workspace owner on tickets
# (BUG-2103), refusal before validation and before confirm's ready return (G12)
# =========================================================================== #

@X1870
def test_atcm_c_71__platform_admin_refused_private_project(db, S, cl):
    """ATCM-C-71 — a platform admin with no membership is refused a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    R = REQ("project", P1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UA)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project {P1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X1870
def test_atcm_c_72__platform_admin_refused_private_component(db, S, cl):
    """ATCM-C-72 — a platform admin with no membership is refused a component of a private project
    Rules: create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    R = REQ("project_component", C1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        create(db, S, R, S.UA)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"project_component {C1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_c_73__workspace_owner_attaches_to_ticket(db, S):
    """ATCM-C-73 — the workspace owner with a plain role may attach to another member's ticket.
    Rules: create_pending_attachment R1b [BUG-2103]; PR-2, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    member(db, S, UX, "ground-team")
    set_owner(db, S.W1, UX)
    H1 = ticket(db, S, "HT-1")
    R = REQ("support_ticket", H1.id)
    result = create(db, S, R, UX)
    # Then 1
    assert result.upload_status == "pending"
    assert result.uploaded_by == UX.id
    # Then 2
    assert len(links_of(db, result)) == 1


@X2091
def test_atcm_pg_44__platform_admin_refused_private_project(db, S, cl):
    """ATCM-PG-44 — refused: a platform admin does not open a private project's attachment
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UA.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_45__platform_admin_refused_private_component(db, S, cl):
    """ATCM-PG-45 — refused: a platform admin does not open a private project's component attachment
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UA.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_pg_46__workspace_owner_reaches_ticket(db, S, cl):
    """ATCM-PG-46 — allowed: the workspace owner with a plain role reaches another member's ticket.
    Rules: get_pdf_page_image R2 [BUG-2103]; PR-2, PR-3, PR-5 (via pg)."""
    UX = make_profile(db, name="Nia Shah")
    member(db, S, UX, "ground-team")
    set_owner(db, S.W1, UX)
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "support_ticket", H1)
    result = pg(db, UX, attachment_id=A1.id, workspace_id=S.W1.id, page=1)
    # Then 1
    assert result["page"] == 1
    assert result["page_count"] is None
    # Then 2
    assert cl.bsu.call_count == 1


@X2091
def test_atcm_pg_47__hidden_page_zero_not_found(db, S, cl):
    """ATCM-PG-47 — refused before validation: a hidden attachment with page 0 answers not found, not the page error
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4 (G12)."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True, pdf=True)
    link(db, S, A1, "project", P1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=0, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_pg_48__hidden_pending_not_found(db, S, cl):
    """ATCM-PG-48 — refused before validation: a hidden pending PDF answers not found, not "not ready"
    Rules: get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4 (G12)."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", pdf=True)
    link(db, S, A1, "support_ticket", H1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=S.W1.id, page=1, user_id=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_100__platform_admin_refused_private_project(db, S, cl):
    """ATCM-CF-100 — refused: a platform admin does not confirm a private project's attachment
    Rules: confirm_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UA.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_101__platform_admin_refused_private_component(db, S, cl):
    """ATCM-CF-101 — refused: a platform admin does not confirm a private project's component attachment
    Rules: confirm_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UA.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


def test_atcm_cf_102__workspace_owner_confirms_on_ticket(db, S):
    """ATCM-CF-102 — allowed: the workspace owner with a plain role confirms on another member's ticket.
    Rules: confirm_attachment R1a [BUG-2103]; PR-2, PR-3, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    member(db, S, UX, "ground-team")
    set_owner(db, S.W1, UX)
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1")
    link(db, S, A1, "support_ticket", H1)
    result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=UX.id)
    # Then 1
    assert status_of(result) == "ready"
    # Then 2
    assert len(ledger_of(db, A1)) == 1


@X2091
def test_atcm_cf_103__hidden_ready_private_project_not_found(db, S, cl):
    """ATCM-CF-103 — refused before the ready return: a private project's ready attachment answers not found and leaks nothing
    Rules: confirm_attachment R1a, R2 [BUG-2091]; PR-3, PR-4 (G12)."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert "photo.jpg" not in str(exc.value)
    assert "dev/a1" not in str(exc.value)
    assert "http" not in str(exc.value)
    # Then 4
    assert state == CLEAN
    # Then 5
    assert counts(db) == before
    # Then 6
    assert now_of(db, A1) == snap_a1
    # Then 7
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_104__hidden_ready_ticket_not_found(db, S, cl):
    """ATCM-CF-104 — refused before the ready return: another member's ticket's ready attachment answers not found and leaks nothing
    Rules: confirm_attachment R1a, R2 [BUG-2091]; PR-3, PR-4 (G12)."""
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "support_ticket", H1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert "photo.jpg" not in str(exc.value)
    assert "dev/a1" not in str(exc.value)
    assert "http" not in str(exc.value)
    # Then 4
    assert state == CLEAN
    # Then 5
    assert counts(db) == before
    # Then 6
    assert now_of(db, A1) == snap_a1
    # Then 7
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_cf_105__hidden_no_public_id_not_found(db, S, cl):
    """ATCM-CF-105 — refused before validation: a hidden attachment with no public_id answers not found, not "no public_id"
    Rules: confirm_attachment R1a, R3 [BUG-2091]; PR-3, PR-4 (G12)."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", public_id=None)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    # Then 1
    with pytest.raises(AttachmentNotFoundError) as exc:
        AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, performed_by=S.UG.id)
    state = session_state(db)
    # Then 2
    assert str(exc.value) == f"Attachment {A1.id} not found."
    # Then 3
    assert state == CLEAN
    # Then 4
    assert counts(db) == before
    # Then 5
    assert now_of(db, A1) == snap_a1
    # Then 6
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_64__platform_admin_refused_private_project(db, S, cl):
    """ATCM-D-64 — refused: a platform admin does not delete a private project's attachment
    Rules: delete_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project", P1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UA.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


@X2091
def test_atcm_d_65__platform_admin_refused_private_component(db, S, cl):
    """ATCM-D-65 — refused: a platform admin does not delete a private project's component attachment
    Rules: delete_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5."""
    P1 = proj(db, S, "Tender 7", private=True)
    C1 = comp(db, P1, "Frame")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "project_component", C1)
    before = counts(db)
    snap_a1 = snap(db, A1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=S.UA.id)
    state = session_state(db)
    # Then 1
    assert result is None
    # Then 2
    assert state == CLEAN
    # Then 3
    assert counts(db) == before
    # Then 4
    assert now_of(db, A1) == snap_a1
    # Then 5
    assert called(cl) == UNTOUCHED


def test_atcm_d_66__workspace_owner_deletes_on_ticket(db, S):
    """ATCM-D-66 — allowed: the workspace owner with a plain role deletes on another member's ticket.
    Rules: delete_attachment R1a [BUG-2103]; PR-2, PR-3, PR-5."""
    UX = make_profile(db, name="Nia Shah")
    member(db, S, UX, "ground-team")
    set_owner(db, S.W1, UX)
    H1 = ticket(db, S, "HT-1")
    A1 = att(db, S, "dev/a1", ready=True)
    link(db, S, A1, "support_ticket", H1)
    result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=S.W1.id, deleted_by=UX.id)
    # Then 1
    assert result is A1
    # Then 2
    row = reread(db, Attachment, A1.id)
    assert row.is_deleted is True
    assert row.deleted_by == UX.id
