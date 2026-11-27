"""Unit tests for app/services/approval_notification_service.py.

Implements tests/unit/services/approval_notification_service.cases.md
(revision 4), one test per card, in card order. Real Postgres session (`db`
fixture), rolled back after each test. Nothing is patched except the commit /
rollback spies Conventions name (they still call the real method).

Every test builds the Standing rows (autouse fixture `st`), which first runs
`SET LOCAL session_replication_role = replica` for the whole test. Card row
names are the lower-case attributes of `st` (UA -> st.ua, `W1.id` -> st.w1.id);
`# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import os
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_item import ExpenseOrderItem
from app.models.notification import Notification
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.workspace_member import WorkspaceMember
from app.services import approval_notification_service as ans
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

MISSING = 999999999


def T(k):
    return datetime(2026, 3, 4, k, 0, 0)  # noqa: DTZ001


# Convention "GN(n)": the per-process number suffix for transfer and sales
# order numbers (unique across all workspaces today).
def GN(n):
    return f"{n}-{os.getpid()}"


BUG_1205 = pytest.mark.xfail(strict=True, reason="BUG-1205: Sales order approvers are never notified")
BUG_1202 = pytest.mark.xfail(strict=True, reason="BUG-1202: Purchase order with no approvers counts as fully approved")
BUG_1203 = pytest.mark.xfail(strict=True, reason="BUG-1203: Transfer order with no approvers counts as fully approved")
BUG_755 = pytest.mark.xfail(
    strict=True,
    reason="BUG-755: Order with no approvers and no explicit requirement counts as fully approved",
)

DRAFT = "draft|Linked payable invoice is in draft — confirm when details look correct"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, in this order)
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def st(db):
    db.execute(text("SET LOCAL session_replication_role = replica"))
    s = SimpleNamespace()
    s.w0 = make_workspace(db)
    s.w1 = make_workspace(db)
    s.w2 = make_workspace(db)
    for attr, name in [
        ("uz0", "Zia"), ("ua", "Ann"), ("ub", "Bob"), ("uc", "Cara"), ("ud", "Dina"),
        ("us", "Sue"), ("ui", "Ivy"), ("uv", "Val"), ("un", "Nora"), ("uz2", "Zed"),
    ]:
        setattr(s, attr, make_profile(db, name=name))
    for ws, u, status in [
        (s.w1, s.ua, "active"), (s.w1, s.ub, "active"), (s.w1, s.uc, "active"), (s.w1, s.ud, "active"),
        (s.w1, s.us, "suspended"), (s.w1, s.ui, "invited"), (s.w1, s.uv, "inactive"),
        (s.w0, s.uz0, "active"), (s.w2, s.uz2, "active"),
    ]:
        _add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role="member", status=status))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows. `ws=` is "W2 x" / "W0 x"; keyword arguments are
# the columns listed after "but".
# --------------------------------------------------------------------------- #

def po(db, st, n, ws=None, **but):
    f = {
        "workspace_id": (ws or st.w1).id, "po_number": n, "destination_type": "storage", "destination_id": MISSING,
        "subtotal": Decimal("0.00"), "total_amount": Decimal("0.00"), "current_status_id": MISSING,
        "created_by": st.uc.id, "supplier_confirmed": False, "details_confirmed": False, "items_confirmed": False,
        "invoice_confirmed": False, "required_approvals": None,
    }
    f.update(but)
    return _add(db, PurchaseOrder(**f))


def ready_po(db, st, n, **but):
    return po(db, st, n, **{"supplier_confirmed": True, "details_confirmed": True, "items_confirmed": True, **but})


def to_(db, st, n, **but):
    f = {
        "workspace_id": st.w1.id, "transfer_number": GN(n), "source_location_type": "storage", "source_location_id": MISSING,
        "destination_location_type": "storage", "destination_location_id": 999999998, "current_status_id": MISSING,
        "created_by": st.uc.id, "required_approvals": None,
    }
    f.update(but)
    return _add(db, TransferOrder(**f))


def to_line(db, st, t, **but):
    f = {"workspace_id": st.w1.id, "transfer_order_id": t.id, "line_number": 1, "item_id": MISSING, "quantity": Decimal(1)}
    f.update(but)
    return _add(db, TransferOrderItem(**f))


def eo(db, st, n, **but):
    f = {
        "workspace_id": st.w1.id, "expense_number": n, "expense_category": "other", "expense_date": date(2026, 3, 1),
        "subtotal": Decimal("0.00"), "total_amount": Decimal("0.00"), "created_by": st.uc.id, "description": "Order One",
        "required_approvals": None,
    }
    f.update(but)
    return _add(db, ExpenseOrder(**f))


def eo_line(db, st, e, **but):
    f = {
        "workspace_id": st.w1.id, "expense_order_id": e.id, "line_number": 1, "description": "Paper", "quantity": Decimal(1),
        "unit_price": Decimal(1), "line_subtotal": Decimal(1),
    }
    f.update(but)
    return _add(db, ExpenseOrderItem(**f))


def wo(db, st, n, ws=None, **but):
    f = {
        "workspace_id": (ws or st.w1).id, "work_order_number": n, "title": "Order One", "factory_id": MISSING,
        "work_order_type_id": MISSING, "created_by": st.uc.id, "required_approvals": None,
    }
    f.update(but)
    return _add(db, WorkOrder(**f))


def so(db, st, n, **but):
    f = {
        "workspace_id": st.w1.id, "sales_order_number": GN(n), "account_id": MISSING, "factory_id": MISSING,
        "order_date": date(2026, 3, 1), "total_amount": Decimal("0.00"), "current_status_id": MISSING, "created_by": st.uc.id,
    }
    f.update(but)
    return _add(db, SalesOrder(**f))


_APPROVER = {
    "po": (PurchaseOrderApprover, "purchase_order_id"),
    "to": (TransferOrderApprover, "transfer_order_id"),
    "eo": (ExpenseOrderApprover, "expense_order_id"),
    "wo": (WorkOrderApprover, "work_order_id"),
    "so": (SalesOrderApprover, "sales_order_id"),
}


def _appr(kind, db, st, o, u, k, ws=None, approved=False):
    model, fk = _APPROVER[kind]
    f = {"workspace_id": (ws or st.w1).id, fk: o.id, "user_id": u.id, "assigned_at": T(k)}
    if approved:
        f.update(approved=True, approved_at=T(12))
    return _add(db, model(**f))


def poa(*a, **k):
    return _appr("po", *a, **k)


def toa(*a, **k):
    return _appr("to", *a, **k)


def eoa(*a, **k):
    return _appr("eo", *a, **k)


def woa(*a, **k):
    return _appr("wo", *a, **k)


def soa(*a, **k):
    return _appr("so", *a, **k)


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #

def notes(db):
    db.expire_all()
    return db.query(Notification).order_by(Notification.id).all()


def to(db, u):
    return [n for n in notes(db) if n.recipient_user_id == u.id]


def recips(db):
    return sorted(n.recipient_user_id for n in notes(db))


def note(db, u):
    return to(db, u)[0]


def spies(db):
    return patch.object(db, "commit", wraps=db.commit), patch.object(db, "rollback", wraps=db.rollback)


# =========================================================================== #
# format_order_ref
# =========================================================================== #

@pytest.mark.parametrize(
    ("etype", "eid", "expected"),
    [
        pytest.param("purchase_order", 12, "PO-12", id="APN-FR-01"),
        pytest.param("transfer_order", 7, "TO-7", id="APN-FR-02"),
        pytest.param("expense_order", 485393, "EXP-485393", id="APN-FR-03"),
        pytest.param("work_order", 3, "WO-3", id="APN-FR-04"),
        pytest.param("project_component", 3, "project component #3", id="APN-FR-05"),
        pytest.param("x", 1, "x #1", id="APN-FR-06"),
    ],
)
def test_apn_fr_01_06__reference_text(etype, eid, expected):
    """APN-FR-01 … FR-06 — known prefixes use the id; other types become words and a number.
    Rules: format_order_ref R1, R2."""
    result = ans.format_order_ref(etype, eid)
    # Then 1
    assert result == expected


@BUG_1205
def test_apn_fr_07__sales_order_reference():
    """APN-FR-07 — a sales order is "SO-<id>".
    Rules: format_order_ref R2a [BUG-1205]."""
    result = ans.format_order_ref("sales_order", 5)
    # Then 1
    assert result == "SO-5"


# =========================================================================== #
# _active_member_ids
# =========================================================================== #

def test_apn_am_01__only_active_members_of_workspace(db, st):
    """APN-AM-01 — only active members of that workspace.
    Rules: _active_member_ids R1."""
    result = ans._active_member_ids(db, st.w1.id)
    # Then 1
    assert result == {st.ua.id, st.ub.id, st.uc.id, st.ud.id}
    # Then 2
    assert isinstance(result, set)


def test_apn_am_02__other_workspace_own_members(db, st):
    """APN-AM-02 — the other workspaces give their own members.
    Rules: _active_member_ids R1."""
    result = ans._active_member_ids(db, st.w2.id)
    # Then 1
    assert result == {st.uz2.id}


def test_apn_am_03__unknown_workspace_empty(db, st):
    """APN-AM-03 — an unknown workspace gives an empty set.
    Rules: _active_member_ids R1."""
    result = ans._active_member_ids(db, MISSING)
    # Then 1
    assert result == set()


# =========================================================================== #
# _notify_user
# =========================================================================== #

def test_apn_nu_01__active_member_gets_one_row(db, st):
    """APN-NU-01 — an active member gets one row with exactly the given values.
    Rules: _notify_user R1."""
    result = ans._notify_user(
        db, workspace_id=st.w1.id, recipient_user_id=st.ub.id, actor_user_id=st.ua.id,
        notification_type="approval_pending", entity_type="purchase_order", entity_id=41,
        source_type="order", source_id=42, preview="Hello",
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert len(notes(db)) == 1
    # Then 4
    assert len(to(db, st.ub)) == 1
    # Then 5
    n = note(db, st.ub)
    assert n.workspace_id == st.w1.id
    assert n.actor_user_id == st.ua.id
    assert n.notification_type == "approval_pending"
    assert n.entity_type == "purchase_order"
    assert n.entity_id == 41
    assert n.source_type == "order"
    assert n.source_id == 42
    assert n.preview == "Hello"
    assert n.is_read is False


def test_apn_nu_02__preview_left_out_is_null(db, st):
    """APN-NU-02 — preview left out is stored NULL.
    Rules: _notify_user R1."""
    result = ans._notify_user(
        db, workspace_id=st.w1.id, recipient_user_id=st.ub.id, actor_user_id=st.ua.id,
        notification_type="section_confirm", entity_type="work_order", entity_id=5,
        source_type="section", source_id=5,
    )
    # Then 1
    assert result is None
    # Then 2
    assert len(to(db, st.ub)) == 1
    # Then 3
    n = note(db, st.ub)
    assert n.preview is None
    assert n.notification_type == "section_confirm"


def test_apn_nu_03__suspended_member_gets_nothing(db, st):
    """APN-NU-03 — a suspended member gets nothing.
    Rules: _notify_user R2."""
    result = ans._notify_user(
        db, workspace_id=st.w1.id, recipient_user_id=st.us.id, actor_user_id=st.ua.id,
        notification_type="approval_pending", entity_type="purchase_order", entity_id=41,
        source_type="order", source_id=41, preview="Hello",
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert len(notes(db)) == 0


@pytest.mark.parametrize(
    ("who", "where"),
    [
        pytest.param("ui", "w1", id="APN-NU-04"),
        pytest.param("uv", "w1", id="APN-NU-05"),
        pytest.param("uz0", "w1", id="APN-NU-06"),
        pytest.param("uz2", "w1", id="APN-NU-07"),
        pytest.param("ub", "w2", id="APN-NU-08"),
        pytest.param("un", "w1", id="APN-NU-09"),
    ],
)
def test_apn_nu_04_09__non_active_recipient_gets_nothing(db, st, who, where):
    """APN-NU-04 … NU-09 — invited, inactive, other-workspace-only, wrong workspace, no membership: nothing.
    Rules: _notify_user R2."""
    result = ans._notify_user(
        db, workspace_id=getattr(st, where).id, recipient_user_id=getattr(st, who).id, actor_user_id=st.ua.id,
        notification_type="approval_pending", entity_type="purchase_order", entity_id=41,
        source_type="order", source_id=41, preview="Hello",
    )
    # Then 1
    assert result is None
    # Then 2
    assert len(notes(db)) == 0


def test_apn_nu_10__unknown_actor_fails_write(db, st):
    """APN-NU-10 — an unknown actor makes the write fail.
    Rules: _notify_user Errors (NotificationDAO.create R4)."""
    db.execute(text("SET LOCAL session_replication_role = origin"))
    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            ans._notify_user(
                db, workspace_id=st.w1.id, recipient_user_id=st.ub.id, actor_user_id=MISSING,
                notification_type="approval_pending", entity_type="purchase_order", entity_id=41,
                source_type="order", source_id=41, preview="Hello",
            )
    # Then 2
    assert len(notes(db)) == 0


def test_apn_nu_11__recipient_may_be_actor(db, st):
    """APN-NU-11 — the recipient may be the actor.
    Rules: _notify_user R3."""
    result = ans._notify_user(
        db, workspace_id=st.w1.id, recipient_user_id=st.ua.id, actor_user_id=st.ua.id,
        notification_type="invoice_action", entity_type="purchase_order", entity_id=41,
        source_type="invoice", source_id=9, preview="Hi",
    )
    # Then 1
    assert result is None
    # Then 2
    assert len(to(db, st.ua)) == 1
    # Then 3
    n = note(db, st.ua)
    assert n.actor_user_id == st.ua.id
    assert n.source_id == 9


def test_apn_nu_12__no_commit(db, st):
    """APN-NU-12 — writes but never commits or rolls back.
    Rules: _notify_user R1 (no commit; spec Overview)."""
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        ans._notify_user(
            db, workspace_id=st.w1.id, recipient_user_id=st.ub.id, actor_user_id=st.ua.id,
            notification_type="approval_pending", entity_type="purchase_order", entity_id=41,
            source_type="order", source_id=41, preview="Hello",
        )
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# _actor_name
# =========================================================================== #

def test_apn_an_01__none_is_someone(db, st):
    """APN-AN-01 — no user id gives "Someone".
    Rules: _actor_name R1."""
    result = ans._actor_name(db, None)
    # Then 1
    assert result == "Someone"


def test_apn_an_02__named_profile(db, st):
    """APN-AN-02 — a named profile gives its name.
    Rules: _actor_name R2."""
    result = ans._actor_name(db, st.ua.id)
    # Then 1
    assert result == "Ann"


def test_apn_an_03__name_not_trimmed_any_workspace(db, st):
    """APN-AN-03 — the name is not trimmed, and any workspace's profile is named.
    Rules: _actor_name R2."""
    pr = make_profile(db, name=" Rahim ")
    result = ans._actor_name(db, pr.id)
    # Then 1
    assert result == " Rahim "


def test_apn_an_04__empty_name(db, st):
    """APN-AN-04 — an empty name gives "User <id>".
    Rules: _actor_name R3."""
    pe = make_profile(db, name="")
    result = ans._actor_name(db, pe.id)
    # Then 1
    assert result == f"User {pe.id}"


def test_apn_an_06__unknown_id(db, st):
    """APN-AN-06 — an unknown id gives "User <id>".
    Rules: _actor_name R3."""
    result = ans._actor_name(db, MISSING)
    # Then 1
    assert result == "User 999999999"


# =========================================================================== #
# _approval_summary
# =========================================================================== #

def test_apn_su_01__po_three_one_approved(db, st):
    """APN-SU-01 — purchase order: three approvers, one approved, no requirement.
    Rules: _approval_summary R1."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, approved=True)
    poa(db, st, p, st.us, 11)
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (1, 3, False)


def test_apn_su_02__to_two_one_approved(db, st):
    """APN-SU-02 — transfer order: two approvers, one approved.
    Rules: _approval_summary R1."""
    t = to_(db, st, "TO-1")
    toa(db, st, t, st.ub, 9, approved=True)
    toa(db, st, t, st.ud, 10)
    result = ans._approval_summary(db, "transfer_order", t.id, st.w1.id)
    # Then 1
    assert result == (1, 2, False)


def test_apn_su_03__eo_requirement_met(db, st):
    """APN-SU-03 — expense order: the requirement is met.
    Rules: _approval_summary R1."""
    e = eo(db, st, "EXP-1", required_approvals=1)
    eoa(db, st, e, st.ub, 9, approved=True)
    eoa(db, st, e, st.ud, 10)
    result = ans._approval_summary(db, "expense_order", e.id, st.w1.id)
    # Then 1
    assert result == (1, 1, True)


def test_apn_su_04__wo_explicit_requirement(db, st):
    """APN-SU-04 — work order: an explicit requirement wins over the row count.
    Rules: _approval_summary R1."""
    o = wo(db, st, "WO-1", required_approvals=3)
    woa(db, st, o, st.ub, 9, approved=True)
    result = ans._approval_summary(db, "work_order", o.id, st.w1.id)
    # Then 1
    assert result == (1, 3, False)


def test_apn_su_05__requirement_zero_met(db, st):
    """APN-SU-05 — requirement 0 is met with approvers pending.
    Rules: _approval_summary R1."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (0, 0, True)


def test_apn_su_06__negative_requirement(db, st):
    """APN-SU-06 — a negative requirement is used as given.
    Rules: _approval_summary R1."""
    p = po(db, st, "PO-1", required_approvals=-1)
    poa(db, st, p, st.ub, 9)
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (0, -1, True)


@BUG_1202
def test_apn_su_07__po_no_approvers_needs_one(db, st):
    """APN-SU-07 — purchase order with no approvers and no requirement needs one approval.
    Rules: _approval_summary R2 [BUG-1202]."""
    p = po(db, st, "PO-1")
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (0, 1, False)


@BUG_1203
def test_apn_su_08__to_no_approvers_needs_one(db, st):
    """APN-SU-08 — transfer order with no approvers and no requirement needs one approval.
    Rules: _approval_summary R2 [BUG-1203]."""
    t = to_(db, st, "TO-1")
    result = ans._approval_summary(db, "transfer_order", t.id, st.w1.id)
    # Then 1
    assert result == (0, 1, False)


@BUG_755
def test_apn_su_09__eo_no_approvers_needs_one(db, st):
    """APN-SU-09 — expense order with no approvers and no requirement needs one approval.
    Rules: _approval_summary R2 [BUG-755]."""
    e = eo(db, st, "EXP-1")
    result = ans._approval_summary(db, "expense_order", e.id, st.w1.id)
    # Then 1
    assert result == (0, 1, False)


def test_apn_su_10__wo_never_had_approver(db, st):
    """APN-SU-10 — work order that never had an approver stays 0 of 0, met.
    Rules: _approval_summary R2."""
    o = wo(db, st, "WO-1")
    result = ans._approval_summary(db, "work_order", o.id, st.w1.id)
    # Then 1
    assert result == (0, 0, True)


def test_apn_su_11__other_workspace_approvers_not_counted(db, st):
    """APN-SU-11 — approver rows of W0 and W2 on the same order id are not counted.
    Rules: _approval_summary R3."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ua, 8, ws=st.w0, approved=True)
    poa(db, st, p, st.ub, 9, approved=True)
    poa(db, st, p, st.ud, 10)
    poa(db, st, p, st.uc, 11, ws=st.w2, approved=True)
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (1, 2, False)


def test_apn_su_12__more_approved_than_required(db, st):
    """APN-SU-12 — more approved than required.
    Rules: _approval_summary R4."""
    p = po(db, st, "PO-1", required_approvals=1)
    poa(db, st, p, st.ub, 9, approved=True)
    poa(db, st, p, st.ud, 10, approved=True)
    result = ans._approval_summary(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == (2, 1, True)


def test_apn_su_13__unknown_po_404(db, st):
    """APN-SU-13 — unknown purchase order id is 404.
    Rules: _approval_summary R5."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "purchase_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order with ID 999999999 not found"


def test_apn_su_14__w2_po_404_in_w1(db, st):
    """APN-SU-14 — a purchase order of W2 is 404 in W1.
    Rules: _approval_summary R5."""
    p9 = po(db, st, "PO-9", ws=st.w2)
    poa(db, st, p9, st.uz2, 9, ws=st.w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "purchase_order", p9.id, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {p9.id} not found"


def test_apn_su_15__unknown_to_404(db, st):
    """APN-SU-15 — unknown transfer order id is 404.
    Rules: _approval_summary R5."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "transfer_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order with ID 999999999 not found"


def test_apn_su_16__unknown_eo_404(db, st):
    """APN-SU-16 — unknown expense order id is 404.
    Rules: _approval_summary R5."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "expense_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Expense order with ID 999999999 not found"


def test_apn_su_17__w0_wo_404_in_w1(db, st):
    """APN-SU-17 — a work order of W0 is 404 in W1.
    Rules: _approval_summary R5."""
    o0 = wo(db, st, "WO-0", ws=st.w0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "work_order", o0.id, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order with ID {o0.id} not found"


def test_apn_su_18__unknown_type(db, st):
    """APN-SU-18 — an unknown type gives 0 of 0, met, with no lookup.
    Rules: _approval_summary R6."""
    result = ans._approval_summary(db, "project_component", MISSING, st.w1.id)
    # Then 1
    assert result == (0, 0, True)


@BUG_1205
def test_apn_su_19__sales_approvers_counted(db, st):
    """APN-SU-19 — sales order: approvers are counted.
    Rules: _approval_summary R6a [BUG-1205]."""
    s = so(db, st, "SO-1")
    soa(db, st, s, st.ub, 9, approved=True)
    soa(db, st, s, st.ud, 10)
    result = ans._approval_summary(db, "sales_order", s.id, st.w1.id)
    # Then 1
    assert result == (1, 2, False)


@BUG_1205
def test_apn_su_20__sales_no_approvers_needs_one(db, st):
    """APN-SU-20 — sales order with no approvers and no requirement needs one approval.
    Rules: _approval_summary R6a [BUG-1205, BUG-736]."""
    s = so(db, st, "SO-1")
    result = ans._approval_summary(db, "sales_order", s.id, st.w1.id)
    # Then 1
    assert result == (0, 1, False)


@BUG_1205
def test_apn_su_21__unknown_sales_404(db, st):
    """APN-SU-21 — an unknown sales order id is 404.
    Rules: _approval_summary R6a [BUG-1205]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "sales_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Sales order with ID {MISSING} not found"


@BUG_1205
def test_apn_su_22__w2_sales_404(db, st):
    """APN-SU-22 — another workspace's sales order id is 404.
    Rules: _approval_summary R6a [BUG-1205]."""
    s9 = so(db, st, "SO-9", workspace_id=st.w2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._approval_summary(db, "sales_order", s9.id, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Sales order with ID {s9.id} not found"


# =========================================================================== #
# build_approval_preview
# =========================================================================== #

def test_apn_bp_01__requirement_zero(db, st):
    """APN-BP-01 — requirement 0 reads "Ready for review".
    Rules: build_approval_preview R1."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    result = ans.build_approval_preview(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == "Ready for review"


def test_apn_bp_02__negative_requirement(db, st):
    """APN-BP-02 — a negative requirement reads "Ready for review".
    Rules: build_approval_preview R1."""
    p = po(db, st, "PO-1", required_approvals=-1)
    result = ans.build_approval_preview(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == "Ready for review"


def test_apn_bp_03__wo_without_approvers(db, st):
    """APN-BP-03 — work order without approvers reads "Ready for review".
    Rules: build_approval_preview R1."""
    o = wo(db, st, "WO-1")
    result = ans.build_approval_preview(db, "work_order", o.id, st.w1.id)
    # Then 1
    assert result == "Ready for review"


@BUG_1202
def test_apn_bp_04__po_without_approvers_zero_of_one(db, st):
    """APN-BP-04 — purchase order without approvers reads "0 of 1".
    Rules: build_approval_preview R1 (via _approval_summary R2) [BUG-1202]."""
    p = po(db, st, "PO-1")
    result = ans.build_approval_preview(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == "0 of 1 approval(s) collected"


def test_apn_bp_05__progress_text(db, st):
    """APN-BP-05 — progress text with a positive requirement.
    Rules: build_approval_preview R2."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, approved=True)
    poa(db, st, p, st.uc, 11)
    result = ans.build_approval_preview(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == "1 of 3 approval(s) collected"


def test_apn_bp_06__requirement_one_exceeded(db, st):
    """APN-BP-06 — requirement 1 reads as progress, also when exceeded.
    Rules: build_approval_preview R2."""
    e = eo(db, st, "EXP-1", required_approvals=1)
    eoa(db, st, e, st.ub, 9, approved=True)
    eoa(db, st, e, st.ud, 10, approved=True)
    result = ans.build_approval_preview(db, "expense_order", e.id, st.w1.id)
    # Then 1
    assert result == "2 of 1 approval(s) collected"


def test_apn_bp_07__404_passes_through(db, st):
    """APN-BP-07 — the 404 of the summary passes through.
    Rules: build_approval_preview R3."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans.build_approval_preview(db, "transfer_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order with ID 999999999 not found"


# =========================================================================== #
# _is_approval_ready
# =========================================================================== #

def test_apn_rd_01__po_three_confirmed_ready(db, st):
    """APN-RD-01 — purchase order with the three sections confirmed is ready; invoice ignored.
    Rules: _is_approval_ready R1."""
    p = ready_po(db, st, "PO-1")
    result = ans._is_approval_ready(db, "purchase_order", p, st.w1.id)
    # Then 1
    assert result is True


@pytest.mark.parametrize(
    "but",
    [
        pytest.param({"supplier_confirmed": False, "invoice_confirmed": True}, id="APN-RD-02"),
        pytest.param({"details_confirmed": False}, id="APN-RD-03"),
        pytest.param({"items_confirmed": False}, id="APN-RD-04"),
    ],
)
def test_apn_rd_02_04__po_section_missing_not_ready(db, st, but):
    """APN-RD-02 … RD-04 — a purchase order missing one of the three sections is not ready.
    Rules: _is_approval_ready R1."""
    p = ready_po(db, st, "PO-1", **but)
    result = ans._is_approval_ready(db, "purchase_order", p, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_05__in_memory_values_read(db, st):
    """APN-RD-05 — the in-memory values are read, not the stored row.
    Rules: _is_approval_ready R6."""
    p = ready_po(db, st, "PO-1", items_confirmed=False)
    p.items_confirmed = True
    result = ans._is_approval_ready(db, "purchase_order", p, st.w1.id)
    # Then 1
    assert result is True


def test_apn_rd_06__eo_ready(db, st):
    """APN-RD-06 — expense order that meets every check is ready.
    Rules: _is_approval_ready R2."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e)
    result = ans._is_approval_ready(db, "expense_order", e, st.w1.id)
    # Then 1
    assert result is True


def test_apn_rd_07__eo_no_lines(db, st):
    """APN-RD-07 — expense order with no lines is not ready.
    Rules: _is_approval_ready R2."""
    e = eo(db, st, "EXP-1")
    result = ans._is_approval_ready(db, "expense_order", e, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_08__eo_line_in_w2(db, st):
    """APN-RD-08 — expense order whose only line is in W2 is not ready.
    Rules: _is_approval_ready R2."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e, workspace_id=st.w2.id)
    result = ans._is_approval_ready(db, "expense_order", e, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_09__eo_quantity_zero(db, st):
    """APN-RD-09 — expense order with a quantity-0 line is not ready.
    Rules: _is_approval_ready R2."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e, quantity=Decimal(0))
    result = ans._is_approval_ready(db, "expense_order", e, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_10__wo_title_and_factory(db, st):
    """APN-RD-10 — work order with a title and a factory is ready.
    Rules: _is_approval_ready R3."""
    o = wo(db, st, "WO-1", title=" x ")
    result = ans._is_approval_ready(db, "work_order", o, st.w1.id)
    # Then 1
    assert result is True


def test_apn_rd_11__wo_blank_title(db, st):
    """APN-RD-11 — work order with a blank title is not ready.
    Rules: _is_approval_ready R3."""
    o = wo(db, st, "WO-1", title="   ")
    result = ans._is_approval_ready(db, "work_order", o, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_12__wo_no_factory(db, st):
    """APN-RD-12 — work order without a factory is not ready.
    Rules: _is_approval_ready R3."""
    o = wo(db, st, "WO-1")
    o.factory_id = None
    result = ans._is_approval_ready(db, "work_order", o, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_13__to_ready(db, st):
    """APN-RD-13 — transfer order with a full route and one item is ready.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1")
    to_line(db, st, t)
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is True


@pytest.mark.parametrize(
    "but",
    [
        pytest.param({"source_location_id": 0}, id="APN-RD-14"),
        pytest.param({"destination_location_id": MISSING}, id="APN-RD-16"),
    ],
)
def test_apn_rd_14_16__to_route_not_valid(db, st, but):
    """APN-RD-14, RD-16 — location id 0, or same place at both ends: not ready.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1", **but)
    to_line(db, st, t)
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_15__no_destination_type(db, st):
    """APN-RD-15 — no destination type is not ready.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1")
    to_line(db, st, t)
    t.destination_location_type = None
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_17__same_id_other_type(db, st):
    """APN-RD-17 — same id but a different type is a different place.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1", destination_location_type="factory", destination_location_id=MISSING)
    to_line(db, st, t)
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is True


def test_apn_rd_18__to_no_items(db, st):
    """APN-RD-18 — transfer order with no items is not ready.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1")
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_19__to_item_in_w0(db, st):
    """APN-RD-19 — transfer order whose only item is in W0 is not ready.
    Rules: _is_approval_ready R4."""
    t = to_(db, st, "TO-1")
    to_line(db, st, t, workspace_id=st.w0.id)
    result = ans._is_approval_ready(db, "transfer_order", t, st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_20__unknown_type_never_ready(db, st):
    """APN-RD-20 — an unknown type is never ready.
    Rules: _is_approval_ready R5."""
    result = ans._is_approval_ready(db, "project_component", SimpleNamespace(id=1), st.w1.id)
    # Then 1
    assert result is False


def test_apn_rd_21__voided_po_by_sections(db, st):
    """APN-RD-21 — a voided purchase order is judged by its sections alone.
    Rules: _is_approval_ready R7."""
    p = ready_po(db, st, "PO-1", voided=True)
    result = ans._is_approval_ready(db, "purchase_order", p, st.w1.id)
    # Then 1
    assert result is True


def test_apn_rd_22__deleted_wo_by_title_factory(db, st):
    """APN-RD-22 — a deleted work order is judged by title and factory alone.
    Rules: _is_approval_ready R7."""
    o = wo(db, st, "WO-1", is_deleted=True, is_active=False)
    result = ans._is_approval_ready(db, "work_order", o, st.w1.id)
    # Then 1
    assert result is True


# =========================================================================== #
# _section_gap_preview
# =========================================================================== #

@pytest.mark.parametrize(
    ("order", "expected"),
    [
        pytest.param(
            SimpleNamespace(supplier_confirmed=True, details_confirmed=False, items_confirmed=False,
                            invoice_confirmed=False),
            "Confirm Order details, Order items before approvals can proceed", id="APN-GP-01",
        ),
        pytest.param(
            SimpleNamespace(),
            "Confirm Supplier, Order details, Order items before approvals can proceed", id="APN-GP-02",
        ),
        pytest.param(
            SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=False,
                            invoice_confirmed=True),
            "Confirm Order items before approvals can proceed", id="APN-GP-03",
        ),
        pytest.param(
            SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True,
                            invoice_confirmed=False),
            "Complete remaining sections before approvals can proceed", id="APN-GP-04",
        ),
    ],
)
def test_apn_gp_01_04__po_gap_text(db, st, order, expected):
    """APN-GP-01 … GP-04 — PO gap text lists the missing labels in order; all three confirmed gives the fallback.
    Rules: _section_gap_preview R1, R2."""
    result = ans._section_gap_preview(db, "purchase_order", order)
    # Then 1
    assert result == expected


def test_apn_gp_05__eo_blank_description(db, st):
    """APN-GP-05 — expense order: the manager's reason (blank description).
    Rules: _section_gap_preview R3."""
    e = eo(db, st, "EXP-1", description="   ")
    eo_line(db, st, e)
    result = ans._section_gap_preview(db, "expense_order", e)
    # Then 1
    assert result == "Add a description before approvals can proceed"


def test_apn_gp_06__eo_no_lines(db, st):
    """APN-GP-06 — expense order: the manager's reason (no lines).
    Rules: _section_gap_preview R3."""
    e = eo(db, st, "EXP-1")
    result = ans._section_gap_preview(db, "expense_order", e)
    # Then 1
    assert result == "Add at least one expense line before approvals can proceed"


def test_apn_gp_07__eo_fallback(db, st):
    """APN-GP-07 — expense order with no reason gets the fallback.
    Rules: _section_gap_preview R3."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e)
    result = ans._section_gap_preview(db, "expense_order", e)
    # Then 1
    assert result == "Complete remaining details before approvals can proceed"


def test_apn_gp_08__eo_quantity_zero_fallback_today(db, st):
    """APN-GP-08 — expense order with a quantity-0 line gets the fallback today (retire when BUG-758 is fixed).
    Rules: _section_gap_preview R3 (spec G2)."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e, quantity=Decimal(0))
    result = ans._section_gap_preview(db, "expense_order", e)
    # Then 1
    assert result == "Complete remaining details before approvals can proceed"


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        pytest.param(SimpleNamespace(title="  ", factory_id=None), "Work order setup is incomplete", id="APN-GP-09"),
        pytest.param(SimpleNamespace(title="Fix", factory_id=None), "Set a factory before approvals can proceed",
                     id="APN-GP-10"),
        pytest.param(SimpleNamespace(title="Fix", factory_id=5),
                     "Complete remaining details before approvals can proceed", id="APN-GP-11"),
    ],
)
def test_apn_gp_09_11__wo_gap_text(db, st, order, expected):
    """APN-GP-09 … GP-11 — work order gap text: blank title, no factory, fallback.
    Rules: _section_gap_preview R4."""
    result = ans._section_gap_preview(db, "work_order", order)
    # Then 1
    assert result == expected


def test_apn_gp_12__to_route_missing(db, st):
    """APN-GP-12 — transfer order with a route field missing.
    Rules: _section_gap_preview R5."""
    t = to_(db, st, "TO-1")
    t.source_location_type = None
    result = ans._section_gap_preview(db, "transfer_order", t)
    # Then 1
    assert result == "Set source and destination before approvals can proceed"


def test_apn_gp_13__to_same_place_says_add_item(db, st):
    """APN-GP-13 — transfer order with the same place at both ends says "add an item".
    Rules: _section_gap_preview R5."""
    t = to_(db, st, "TO-1", destination_location_id=MISSING)
    to_line(db, st, t)
    result = ans._section_gap_preview(db, "transfer_order", t)
    # Then 1
    assert result == "Add at least one item before approvals can proceed"


def test_apn_gp_14__ready_to_says_add_item(db, st):
    """APN-GP-14 — a ready transfer order still says "add an item".
    Rules: _section_gap_preview R5."""
    t = to_(db, st, "TO-1")
    to_line(db, st, t)
    result = ans._section_gap_preview(db, "transfer_order", t)
    # Then 1
    assert result == "Add at least one item before approvals can proceed"


def test_apn_gp_15__unknown_type_none(db, st):
    """APN-GP-15 — an unknown type gives None.
    Rules: _section_gap_preview R6."""
    result = ans._section_gap_preview(db, "project_component", SimpleNamespace(title="x"))
    # Then 1
    assert result is None


# =========================================================================== #
# _pending_approver_ids
# =========================================================================== #

def test_apn_pa_01__po_pending_in_assignment_order(db, st):
    """APN-PA-01 — purchase order: unapproved approvers in assignment order, membership not looked at.
    Rules: _pending_approver_ids R1."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 11)
    poa(db, st, p, st.ud, 10, approved=True)
    poa(db, st, p, st.us, 9)
    result = ans._pending_approver_ids(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == [st.us.id, st.ub.id]


def test_apn_pa_02__other_workspace_rows_left_out(db, st):
    """APN-PA-02 — approver rows of W0 and W2 on the order id are left out.
    Rules: _pending_approver_ids R1."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ua, 8, ws=st.w0)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, ws=st.w2)
    result = ans._pending_approver_ids(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result == [st.ub.id]


def test_apn_pa_03__to_pending(db, st):
    """APN-PA-03 — transfer order pending approvers.
    Rules: _pending_approver_ids R1."""
    t = to_(db, st, "TO-1")
    toa(db, st, t, st.ub, 9, approved=True)
    toa(db, st, t, st.ud, 10)
    result = ans._pending_approver_ids(db, "transfer_order", t.id, st.w1.id)
    # Then 1
    assert result == [st.ud.id]


def test_apn_pa_04__eo_pending(db, st):
    """APN-PA-04 — expense order pending approvers.
    Rules: _pending_approver_ids R1."""
    e = eo(db, st, "EXP-1")
    eoa(db, st, e, st.ud, 10)
    eoa(db, st, e, st.ub, 9)
    result = ans._pending_approver_ids(db, "expense_order", e.id, st.w1.id)
    # Then 1
    assert result == [st.ub.id, st.ud.id]


def test_apn_pa_05__wo_pending(db, st):
    """APN-PA-05 — work order pending approvers.
    Rules: _pending_approver_ids R1."""
    o = wo(db, st, "WO-1")
    woa(db, st, o, st.ub, 9)
    woa(db, st, o, st.ud, 10, approved=True)
    result = ans._pending_approver_ids(db, "work_order", o.id, st.w1.id)
    # Then 1
    assert result == [st.ub.id]


def test_apn_pa_06__unknown_order_empty(db, st):
    """APN-PA-06 — an unknown order id gives [] with no error.
    Rules: _pending_approver_ids R2."""
    result = ans._pending_approver_ids(db, "purchase_order", MISSING, st.w1.id)
    # Then 1
    assert result == []


def test_apn_pa_07__w2_order_in_w1_empty(db, st):
    """APN-PA-07 — an order of W2 asked for in W1 gives [].
    Rules: _pending_approver_ids R2."""
    p9 = po(db, st, "PO-9", ws=st.w2)
    poa(db, st, p9, st.uz2, 9, ws=st.w2)
    result = ans._pending_approver_ids(db, "purchase_order", p9.id, st.w1.id)
    # Then 1
    assert result == []


def test_apn_pa_08__unknown_type_empty(db, st):
    """APN-PA-08 — an unknown type gives [].
    Rules: _pending_approver_ids R3."""
    result = ans._pending_approver_ids(db, "project_component", 1, st.w1.id)
    # Then 1
    assert result == []


@BUG_1205
def test_apn_pa_09__sales_pending(db, st):
    """APN-PA-09 — sales order pending approvers.
    Rules: _pending_approver_ids R3a [BUG-1205]."""
    s = so(db, st, "SO-1")
    soa(db, st, s, st.ub, 9)
    soa(db, st, s, st.ud, 10, approved=True)
    result = ans._pending_approver_ids(db, "sales_order", s.id, st.w1.id)
    # Then 1
    assert result == [st.ub.id]


# =========================================================================== #
# _has_approvers
# =========================================================================== #

def test_apn_ha_01__requirement_without_rows(db, st):
    """APN-HA-01 — a requirement with no approver rows counts as having approvers.
    Rules: _has_approvers R1."""
    p = po(db, st, "PO-1", required_approvals=2)
    result = ans._has_approvers(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result is True


def test_apn_ha_02__rows_with_requirement_zero(db, st):
    """APN-HA-02 — approver rows with requirement 0 count as none.
    Rules: _has_approvers R1."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    result = ans._has_approvers(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result is False


def test_apn_ha_03__requirement_negative(db, st):
    """APN-HA-03 — requirement -1 counts as none.
    Rules: _has_approvers R1."""
    t = to_(db, st, "TO-1", required_approvals=-1)
    toa(db, st, t, st.ub, 9)
    result = ans._has_approvers(db, "transfer_order", t.id, st.w1.id)
    # Then 1
    assert result is False


def test_apn_ha_04__one_row_no_requirement(db, st):
    """APN-HA-04 — one approver row and no requirement.
    Rules: _has_approvers R1."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    result = ans._has_approvers(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result is True


@BUG_1202
def test_apn_ha_05__po_no_approvers_no_requirement(db, st):
    """APN-HA-05 — purchase order with no approvers and no requirement.
    Rules: _has_approvers R1 (via _approval_summary R2) [BUG-1202]."""
    p = po(db, st, "PO-1")
    result = ans._has_approvers(db, "purchase_order", p.id, st.w1.id)
    # Then 1
    assert result is True


def test_apn_ha_06__404_passes_through(db, st):
    """APN-HA-06 — the 404 of the summary passes through.
    Rules: _has_approvers R2."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans._has_approvers(db, "work_order", MISSING, st.w1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order with ID 999999999 not found"


# =========================================================================== #
# notify_approval_assigned
# =========================================================================== #

def test_apn_as_01__assigned_who_and_which_order(db, st):
    """APN-AS-01 — the new approver is told who assigned them, on which order.
    Rules: notify_approval_assigned R1, R2, R4."""
    p = po(db, st, "PO-1")
    r = poa(db, st, p, st.ub, 9)
    result = ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        approver_user_id=st.ub.id, approver_record_id=r.id, order=None,
    )
    # Then 1
    assert result is None
    # Then 2
    assert len(notes(db)) == 1
    # Then 3
    assert len(to(db, st.ub)) == 1
    # Then 4
    n = note(db, st.ub)
    assert n.notification_type == "approval_assigned"
    assert n.entity_type == "purchase_order"
    assert n.entity_id == p.id
    assert n.source_type == "approver"
    assert n.source_id == r.id
    assert n.actor_user_id == st.ua.id
    assert n.workspace_id == st.w1.id
    # Then 5
    assert note(db, st.ub).preview == f"Assigned by Ann on PO-{p.id}"


def test_apn_as_02__no_actor_someone(db, st):
    """APN-AS-02 — no actor reads "Someone".
    Rules: notify_approval_assigned R2."""
    ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="work_order", entity_id=41, actor_user_id=None,
        approver_user_id=st.ub.id, approver_record_id=7, order=None,
    )
    # Then 1
    assert len(to(db, st.ub)) == 1
    # Then 2
    n = note(db, st.ub)
    assert n.preview == "Assigned by Someone on WO-41"
    assert n.actor_user_id is None
    assert n.source_id == 7


def test_apn_as_03__ready_preview_counts_new_approver(db, st):
    """APN-AS-03 — on a ready order the preview carries the progress, counting the new approver.
    Rules: notify_approval_assigned R3."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ud, 9, approved=True)
    poa(db, st, p, st.uc, 10)
    r = poa(db, st, p, st.ub, 11)
    ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        approver_user_id=st.ub.id, approver_record_id=r.id, order=p, ready_for_approval=True,
    )
    # Then 1
    assert len(notes(db)) == 1
    # Then 2
    assert note(db, st.ub).preview == "Assigned by Ann · ready for your approval · 1 of 3 approval(s) collected"


def test_apn_as_04__self_assignment_notified(db, st):
    """APN-AS-04 — an approver who assigned themself is still notified.
    Rules: notify_approval_assigned R5."""
    ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="expense_order", entity_id=485393, actor_user_id=st.ub.id,
        approver_user_id=st.ub.id, approver_record_id=7, order=None,
    )
    # Then 1
    assert len(to(db, st.ub)) == 1
    # Then 2
    n = note(db, st.ub)
    assert n.actor_user_id == st.ub.id
    assert n.preview == "Assigned by Bob on EXP-485393"


def test_apn_as_05__suspended_approver(db, st):
    """APN-AS-05 — a suspended approver is not notified.
    Rules: notify_approval_assigned R1."""
    result = ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
        approver_user_id=st.us.id, approver_record_id=7, order=None,
    )
    # Then 1
    assert result is None
    # Then 2
    assert len(notes(db)) == 0


@pytest.mark.parametrize("who", [pytest.param("uz0", id="APN-AS-06"), pytest.param("uz2", id="APN-AS-07")])
def test_apn_as_06_07__other_workspace_approver(db, st, who):
    """APN-AS-06 / AS-07 — an approver active only in W0 or only in W2 is not notified.
    Rules: notify_approval_assigned R1."""
    ans.notify_approval_assigned(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
        approver_user_id=getattr(st, who).id, approver_record_id=7, order=None,
    )
    # Then 1
    assert len(notes(db)) == 0


def test_apn_as_08__ready_unknown_order_404(db, st):
    """APN-AS-08 — ready preview on an unknown order raises 404 and writes nothing.
    Rules: notify_approval_assigned R6."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans.notify_approval_assigned(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=st.ua.id,
            approver_user_id=st.ub.id, approver_record_id=7, order=None, ready_for_approval=True,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert len(notes(db)) == 0


def test_apn_as_09__no_commit(db, st):
    """APN-AS-09 — writes but never commits or rolls back.
    Rules: notify_approval_assigned R1 (no commit; spec Overview)."""
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        ans.notify_approval_assigned(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
            approver_user_id=st.ub.id, approver_record_id=7, order=None,
        )
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# notify_approval_pending_for_order
# =========================================================================== #

def test_apn_pe_01__every_pending_approver(db, st):
    """APN-PE-01 — every pending approver gets "approval pending" with the progress.
    Rules: notify_approval_pending_for_order R1, R2, R4."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, approved=True)
    poa(db, st, p, st.uc, 11)
    result = ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 3
    assert len(to(db, st.ud)) == 0
    # Then 4
    n = note(db, st.ub)
    assert n.notification_type == "approval_pending"
    assert n.entity_type == "purchase_order"
    assert n.entity_id == p.id
    assert n.source_type == "order"
    assert n.source_id == p.id
    assert n.actor_user_id == st.ua.id
    assert n.preview == "1 of 3 approval(s) collected"
    # Then 5
    n = note(db, st.uc)
    assert n.notification_type == "approval_pending"
    assert n.preview == "1 of 3 approval(s) collected"


def test_apn_pe_02__no_exclusions_actor_notified(db, st):
    """APN-PE-02 — with no exclusions the actor, a pending approver, is notified.
    Rules: notify_approval_pending_for_order R3."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ua, 9)
    poa(db, st, p, st.ub, 10)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        exclude_user_ids=None,
    )
    # Then 1
    assert recips(db) == sorted([st.ua.id, st.ub.id])
    # Then 2
    n = note(db, st.ua)
    assert n.actor_user_id == st.ua.id
    assert n.notification_type == "approval_pending"


def test_apn_pe_03__empty_exclusion_set(db, st):
    """APN-PE-03 — an empty exclusion set excludes nobody.
    Rules: notify_approval_pending_for_order R3."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ua, 9)
    poa(db, st, p, st.ub, 10)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        exclude_user_ids=set(),
    )
    # Then 1
    assert recips(db) == sorted([st.ua.id, st.ub.id])


def test_apn_pe_04__excluded_gets_nothing(db, st):
    """APN-PE-04 — an excluded pending approver gets nothing.
    Rules: notify_approval_pending_for_order R2."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.uc, 10)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        exclude_user_ids={st.ub.id},
    )
    # Then 1
    assert recips(db) == [st.uc.id]


def test_apn_pe_05__non_active_pending_get_nothing(db, st):
    """APN-PE-05 — suspended, invited and inactive pending approvers get nothing.
    Rules: notify_approval_pending_for_order R2."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.us, 8)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ui, 10)
    poa(db, st, p, st.uv, 11)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
    )
    # Then 1
    assert recips(db) == [st.ub.id]
    # Then 2
    assert note(db, st.ub).preview == "0 of 4 approval(s) collected"


def test_apn_pe_06__other_workspace_members(db, st):
    """APN-PE-06 — pending approvers active only in W0 or W2 get nothing.
    Rules: notify_approval_pending_for_order R2."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.uz0, 8)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.uz2, 10)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
    )
    # Then 1
    assert recips(db) == [st.ub.id]


def test_apn_pe_07__other_workspace_rows(db, st):
    """APN-PE-07 — approver rows of W0 and W2 on the order id notify nobody.
    Rules: notify_approval_pending_for_order R2 (via _pending_approver_ids R1)."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.uc, 8, ws=st.w0)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, ws=st.w2)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
    )
    # Then 1
    assert recips(db) == [st.ub.id]
    # Then 2
    assert note(db, st.ub).preview == "0 of 1 approval(s) collected"


def test_apn_pe_08__all_approved_nothing(db, st):
    """APN-PE-08 — every approver already approved: nothing written.
    Rules: notify_approval_pending_for_order R4."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9, approved=True)
    poa(db, st, p, st.ud, 10, approved=True)
    result = ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert len(notes(db)) == 0


def test_apn_pe_09__no_actor_null(db, st):
    """APN-PE-09 — no actor is stored as NULL.
    Rules: notify_approval_pending_for_order R2."""
    o = wo(db, st, "WO-1")
    woa(db, st, o, st.ub, 9)
    ans.notify_approval_pending_for_order(
        db, workspace_id=st.w1.id, entity_type="work_order", entity_id=o.id, actor_user_id=None,
    )
    # Then 1
    assert recips(db) == [st.ub.id]
    # Then 2
    n = note(db, st.ub)
    assert n.actor_user_id is None
    assert n.entity_type == "work_order"
    assert n.entity_id == o.id
    assert n.preview == "0 of 1 approval(s) collected"


def test_apn_pe_10__unknown_order_404(db, st):
    """APN-PE-10 — an unknown order raises 404 even though nobody would be notified.
    Rules: notify_approval_pending_for_order R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans.notify_approval_pending_for_order(
            db, workspace_id=st.w1.id, entity_type="expense_order", entity_id=MISSING, actor_user_id=st.ua.id,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 3
    assert len(notes(db)) == 0


def test_apn_pe_11__no_commit(db, st):
    """APN-PE-11 — writes but never commits or rolls back.
    Rules: notify_approval_pending_for_order R2 (no commit; spec Overview)."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        ans.notify_approval_pending_for_order(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        )
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# notify_section_confirm_needed
# =========================================================================== #

def test_apn_sc_01__creator_gets_reason(db, st):
    """APN-SC-01 — the creator gets the given reason.
    Rules: notify_section_confirm_needed R2, R3."""
    p = po(db, st, "PO-1")
    result = ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        order=p, reason="Please check",
    )
    # Then 1
    assert result is None
    # Then 2
    assert recips(db) == [st.uc.id]
    # Then 3
    n = note(db, st.uc)
    assert n.notification_type == "section_confirm"
    assert n.entity_type == "purchase_order"
    assert n.entity_id == p.id
    assert n.source_type == "section"
    assert n.source_id == p.id
    assert n.actor_user_id == st.ua.id
    assert n.preview == "Please check"


def test_apn_sc_02__no_reason_gap_text(db, st):
    """APN-SC-02 — no reason: the gap text is used.
    Rules: notify_section_confirm_needed R3."""
    p = po(db, st, "PO-1")
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        order=p, reason=None,
    )
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    assert note(db, st.uc).preview == "Confirm Supplier, Order details, Order items before approvals can proceed"


def test_apn_sc_03__empty_reason_gap_text(db, st):
    """APN-SC-03 — an empty reason also falls back to the gap text.
    Rules: notify_section_confirm_needed R3."""
    order = SimpleNamespace(created_by=st.uc.id, supplier_confirmed=True, details_confirmed=True,
                            items_confirmed=False)
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
        order=order, reason="",
    )
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    assert note(db, st.uc).preview == "Confirm Order items before approvals can proceed"


def test_apn_sc_04__unknown_type_null_preview(db, st):
    """APN-SC-04 — an unknown type with no reason stores a NULL preview.
    Rules: notify_section_confirm_needed R3."""
    order = SimpleNamespace(created_by=st.uc.id)
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="project_component", entity_id=3, actor_user_id=st.ua.id,
        order=order,
    )
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    n = note(db, st.uc)
    assert n.preview is None
    assert n.entity_type == "project_component"


def test_apn_sc_05__wo_no_creator(db, st):
    """APN-SC-05 — a work order with no creator: nothing written.
    Rules: notify_section_confirm_needed R1."""
    o = wo(db, st, "WO-1", created_by=None)
    result = ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="work_order", entity_id=o.id, actor_user_id=st.ua.id,
        order=o, reason="Please check",
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert len(notes(db)) == 0


def test_apn_sc_06__no_created_by_attr(db, st):
    """APN-SC-06 — an order object without `created_by`: nothing written.
    Rules: notify_section_confirm_needed R1."""
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
        order=SimpleNamespace(), reason="Please check",
    )
    # Then 1
    assert len(notes(db)) == 0


def test_apn_sc_07__creator_is_actor(db, st):
    """APN-SC-07 — the creator is notified when they are the actor.
    Rules: notify_section_confirm_needed R4."""
    p = po(db, st, "PO-1")
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.uc.id,
        order=p, reason="Please check",
    )
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    assert note(db, st.uc).actor_user_id == st.uc.id


@pytest.mark.parametrize(
    "who",
    [pytest.param("us", id="APN-SC-08"), pytest.param("uz0", id="APN-SC-09"), pytest.param("uz2", id="APN-SC-10")],
)
def test_apn_sc_08_10__creator_not_active_here(db, st, who):
    """APN-SC-08 … SC-10 — a suspended creator, or one active only in W0 / W2, is not notified.
    Rules: notify_section_confirm_needed R2."""
    order = SimpleNamespace(created_by=getattr(st, who).id)
    ans.notify_section_confirm_needed(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
        order=order, reason="Please check",
    )
    # Then 1
    assert len(notes(db)) == 0


def test_apn_sc_11__no_commit(db, st):
    """APN-SC-11 — writes but never commits or rolls back.
    Rules: notify_section_confirm_needed R2 (no commit; spec Overview)."""
    order = SimpleNamespace(created_by=st.uc.id)
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        ans.notify_section_confirm_needed(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=41, actor_user_id=st.ua.id,
            order=order, reason="Please check",
        )
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# notify_invoice_action
# =========================================================================== #

def _ia(db, st, etype, eid, order, action="draft", actor=None):
    return ans.notify_invoice_action(
        db, workspace_id=st.w1.id, entity_type=etype, entity_id=eid, actor_user_id=(actor or st.ua).id,
        invoice_id=77, action=action, order=order,
    )


def test_apn_ia_01__draft_every_approver_and_creator(db, st):
    """APN-IA-01 — draft: every approver and the creator, once each.
    Rules: notify_invoice_action R1, R2, R3, R4, R5."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, approved=True)
    result = ans.notify_invoice_action(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        invoice_id=77, action="draft", order=p,
    )
    # Then 1
    assert result is None
    # Then 2
    assert recips(db) == sorted([st.ub.id, st.uc.id, st.ud.id])
    # Then 3
    n = note(db, st.ub)
    assert n.notification_type == "invoice_action"
    assert n.entity_type == "purchase_order"
    assert n.entity_id == p.id
    assert n.source_type == "invoice"
    assert n.source_id == 77
    assert n.actor_user_id == st.ua.id
    # Then 4
    assert note(db, st.ub).preview == DRAFT
    # Then 5
    assert note(db, st.ud).preview == DRAFT
    # Then 6
    n = note(db, st.uc)
    assert n.notification_type == "invoice_action"
    assert n.source_id == 77


def test_apn_ia_02__confirmed_eo_ref(db, st):
    """APN-IA-02 — confirmed on an expense order names the EXP reference.
    Rules: notify_invoice_action R1."""
    e = eo(db, st, "EXP-1")
    eoa(db, st, e, st.ub, 9)
    _ia(db, st, "expense_order", e.id, e, action="confirmed")
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert note(db, st.ub).preview == f"confirmed|Invoice confirmed on EXP-{e.id} — order locked"


def test_apn_ia_03__other_action_is_confirmed(db, st):
    """APN-IA-03 — any action other than "draft" reads as confirmed.
    Rules: notify_invoice_action R1."""
    o = wo(db, st, "WO-1")
    _ia(db, st, "work_order", o.id, o, action="voided")
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    assert note(db, st.uc).preview == f"confirmed|Invoice confirmed on WO-{o.id} — order locked"


def test_apn_ia_04__empty_action_is_confirmed(db, st):
    """APN-IA-04 — an empty action reads as confirmed.
    Rules: notify_invoice_action R1."""
    t = to_(db, st, "TO-1")
    toa(db, st, t, st.ub, 9)
    _ia(db, st, "transfer_order", t.id, t, action="")
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert note(db, st.ub).preview == f"confirmed|Invoice confirmed on TO-{t.id} — order locked"


def test_apn_ia_05__requirement_zero_approved_left_out(db, st):
    """APN-IA-05 — with requirement 0, approvers who approved are left out.
    Rules: notify_invoice_action R3."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, approved=True)
    _ia(db, st, "purchase_order", p.id, p, action="confirmed")
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert len(to(db, st.ud)) == 0


def test_apn_ia_06__requirement_one_approved_included(db, st):
    """APN-IA-06 — with requirement 1, approvers who approved are included.
    Rules: notify_invoice_action R3."""
    p = po(db, st, "PO-1", required_approvals=1)
    poa(db, st, p, st.ub, 9, approved=True)
    poa(db, st, p, st.ud, 10, approved=True)
    _ia(db, st, "purchase_order", p.id, p, action="confirmed")
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id, st.ud.id])


def test_apn_ia_07__creator_also_approver_once(db, st):
    """APN-IA-07 — a creator who is also an approver gets one notification.
    Rules: notify_invoice_action R2, R4."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.uc, 9)
    poa(db, st, p, st.ub, 10, approved=True)
    _ia(db, st, "purchase_order", p.id, p)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert len(to(db, st.uc)) == 1


def test_apn_ia_08__actor_not_left_out(db, st):
    """APN-IA-08 — the actor is not left out.
    Rules: notify_invoice_action R5."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    _ia(db, st, "purchase_order", p.id, p, actor=st.uc)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert note(db, st.uc).actor_user_id == st.uc.id


def test_apn_ia_09__non_active_approvers(db, st):
    """APN-IA-09 — suspended, invited and inactive approvers get nothing.
    Rules: notify_invoice_action R5."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.us, 8)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ui, 10)
    poa(db, st, p, st.uv, 11, approved=True)
    _ia(db, st, "purchase_order", p.id, p)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])


def test_apn_ia_10__other_workspace_members(db, st):
    """APN-IA-10 — approvers active only in W0 or W2 get nothing.
    Rules: notify_invoice_action R5."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.uz0, 8, approved=True)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.uz2, 10)
    _ia(db, st, "purchase_order", p.id, p)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])


def test_apn_ia_11__other_workspace_rows(db, st):
    """APN-IA-11 — approver rows of W0 and W2 on the order id are no recipients.
    Rules: notify_invoice_action R2, R3."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ua, 8, ws=st.w0, approved=True)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10, ws=st.w2)
    _ia(db, st, "purchase_order", p.id, p, actor=st.uc)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])


def test_apn_ia_12__no_creator_only_approvers(db, st):
    """APN-IA-12 — no creator: only the approvers.
    Rules: notify_invoice_action R4."""
    o = wo(db, st, "WO-1", created_by=None)
    woa(db, st, o, st.ub, 9)
    _ia(db, st, "work_order", o.id, o)
    # Then 1
    assert recips(db) == [st.ub.id]


def test_apn_ia_13__suspended_creator(db, st):
    """APN-IA-13 — a suspended creator gets nothing.
    Rules: notify_invoice_action R4, R5."""
    p = po(db, st, "PO-1", created_by=st.us.id)
    poa(db, st, p, st.ub, 9)
    _ia(db, st, "purchase_order", p.id, p)
    # Then 1
    assert recips(db) == [st.ub.id]


def test_apn_ia_14__unknown_order_404(db, st):
    """APN-IA-14 — an unknown order raises 404 and writes nothing.
    Rules: notify_invoice_action R6."""
    order = SimpleNamespace(created_by=st.uc.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans.notify_invoice_action(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=st.ua.id,
            invoice_id=77, action="draft", order=order,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert len(notes(db)) == 0


def test_apn_ia_15__unknown_type_only_creator(db, st):
    """APN-IA-15 — an unknown type: only the creator.
    Rules: notify_invoice_action R7."""
    order = SimpleNamespace(created_by=st.uc.id)
    _ia(db, st, "project_component", 3, order, action="confirmed")
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    assert note(db, st.uc).preview == "confirmed|Invoice confirmed on project component #3 — order locked"


def test_apn_ia_16__sales_creator_notified(db, st):
    """APN-IA-16 — a sales order's creator is notified.
    Rules: notify_invoice_action R4, R7a (the part that holds today and after BUG-1205)."""
    s = so(db, st, "SO-1")
    soa(db, st, s, st.ub, 9)
    _ia(db, st, "sales_order", s.id, s)
    # Then 1
    assert len(to(db, st.uc)) == 1
    # Then 2
    n = note(db, st.uc)
    assert n.notification_type == "invoice_action"
    assert n.source_type == "invoice"
    assert n.source_id == 77
    assert n.entity_type == "sales_order"


@BUG_1205
def test_apn_ia_17__sales_approvers_notified(db, st):
    """APN-IA-17 — a sales order's approvers are notified too.
    Rules: notify_invoice_action R7a [BUG-1205]."""
    s = so(db, st, "SO-1")
    soa(db, st, s, st.ub, 9)
    soa(db, st, s, st.ud, 10, approved=True)
    _ia(db, st, "sales_order", s.id, s)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id, st.ud.id])


def test_apn_ia_18__no_commit(db, st):
    """APN-IA-18 — writes but never commits or rolls back.
    Rules: notify_invoice_action R5 (no commit; spec Overview)."""
    order = SimpleNamespace(created_by=st.uc.id)
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        _ia(db, st, "project_component", 3, order)
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


@pytest.mark.parametrize(
    ("etype", "build", "appr", "num", "prefix"),
    [
        pytest.param("transfer_order", to_, toa, "TO-1", "TO", id="APN-IA-19"),
        pytest.param("expense_order", eo, eoa, "EXP-1", "EXP", id="APN-IA-20"),
        pytest.param("work_order", wo, woa, "WO-1", "WO", id="APN-IA-21"),
    ],
)
def test_apn_ia_19_21__requirement_two_approved_included(db, st, etype, build, appr, num, prefix):
    """APN-IA-19 … IA-21 — transfer / expense / work order: with requirement 2, an approver who approved is included.
    Rules: notify_invoice_action R3, R2, R5."""
    o = build(db, st, num, required_approvals=2)
    appr(db, st, o, st.ub, 9, approved=True)
    appr(db, st, o, st.us, 10, approved=True)
    appr(db, st, o, st.ud, 11, ws=st.w2, approved=True)
    _ia(db, st, etype, o.id, o, action="confirmed")
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    n = note(db, st.ub)
    assert n.notification_type == "invoice_action"
    assert n.entity_type == etype
    assert n.entity_id == o.id
    assert n.source_id == 77
    # Then 3
    assert note(db, st.ub).preview == f"confirmed|Invoice confirmed on {prefix}-{o.id} — order locked"
    # Then 4
    assert len(to(db, st.us)) == 0
    # Then 5
    assert len(to(db, st.ud)) == 0


# =========================================================================== #
# handle_add_approver
# =========================================================================== #

def test_apn_ad_01__ready_split(db, st):
    """APN-AD-01 — ready order: new approver assigned, other pending approvers reminded, actor left out.
    Rules: handle_add_approver R1, R2."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ud, 9)
    poa(db, st, p, st.ub, 10, approved=True)
    poa(db, st, p, st.ua, 11)
    r = poa(db, st, p, st.uc, 12)
    result = ans.handle_add_approver(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        approver_user_id=st.uc.id, approver_record_id=r.id, order=p,
    )
    # Then 1
    assert result is None
    # Then 2
    assert recips(db) == sorted([st.uc.id, st.ud.id])
    # Then 3
    assert len(to(db, st.ua)) == 0
    # Then 4
    assert [n.notification_type for n in to(db, st.uc)] == ["approval_assigned"]
    # Then 5
    n = note(db, st.uc)
    assert n.preview == "Assigned by Ann · ready for your approval · 1 of 4 approval(s) collected"
    assert n.source_type == "approver"
    assert n.source_id == r.id
    # Then 6
    n = note(db, st.ud)
    assert n.notification_type == "approval_pending"
    assert n.source_type == "order"
    assert n.source_id == p.id
    assert n.preview == "1 of 4 approval(s) collected"
    assert n.actor_user_id == st.ua.id


def test_apn_ad_02__ready_expense_split(db, st):
    """APN-AD-02 — ready expense order: same split.
    Rules: handle_add_approver R1, R2."""
    e = eo(db, st, "EXP-1")
    eo_line(db, st, e)
    eoa(db, st, e, st.ub, 9)
    r = eoa(db, st, e, st.ud, 10)
    ans.handle_add_approver(
        db, workspace_id=st.w1.id, entity_type="expense_order", entity_id=e.id, actor_user_id=st.ua.id,
        approver_user_id=st.ud.id, approver_record_id=r.id, order=e,
    )
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.ud.id])
    # Then 2
    assert len(to(db, st.uc)) == 0
    # Then 3
    n = note(db, st.ud)
    assert n.notification_type == "approval_assigned"
    assert n.preview == "Assigned by Ann · ready for your approval · 0 of 2 approval(s) collected"
    # Then 4
    n = note(db, st.ub)
    assert n.notification_type == "approval_pending"
    assert n.preview == "0 of 2 approval(s) collected"


def test_apn_ad_03__not_ready_creator_asked(db, st):
    """APN-AD-03 — not ready: new approver assigned, creator asked to confirm, nobody reminded.
    Rules: handle_add_approver R1, R3."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ud, 9)
    r = poa(db, st, p, st.ub, 10)
    ans.handle_add_approver(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        approver_user_id=st.ub.id, approver_record_id=r.id, order=p,
    )
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.uc.id])
    # Then 2
    assert len(to(db, st.ud)) == 0
    # Then 3
    n = note(db, st.ub)
    assert n.notification_type == "approval_assigned"
    assert n.preview == f"Assigned by Ann on PO-{p.id}"
    # Then 4
    n = note(db, st.uc)
    assert n.notification_type == "section_confirm"
    assert n.source_type == "section"
    assert n.source_id == p.id
    assert n.actor_user_id == st.ua.id
    # Then 5
    assert note(db, st.uc).preview == "Confirm Supplier, Order details, Order items before approvals can proceed"


def test_apn_ad_04__not_ready_creator_actor_suspended_approver(db, st):
    """APN-AD-04 — not ready, creator is the actor, new approver suspended.
    Rules: handle_add_approver R3."""
    p = po(db, st, "PO-1", supplier_confirmed=True)
    r = poa(db, st, p, st.us, 9)
    ans.handle_add_approver(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.uc.id,
        approver_user_id=st.us.id, approver_record_id=r.id, order=p,
    )
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    n = note(db, st.uc)
    assert n.notification_type == "section_confirm"
    assert n.actor_user_id == st.uc.id
    assert n.preview == "Confirm Order details, Order items before approvals can proceed"


def test_apn_ad_05__no_commit(db, st):
    """APN-AD-05 — writes but never commits or rolls back.
    Rules: handle_add_approver R1 (no commit; spec Overview)."""
    p = po(db, st, "PO-1")
    r = poa(db, st, p, st.ub, 9)
    db.commit()
    c, rs = spies(db)
    with c as cm, rs as rb:
        ans.handle_add_approver(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
            approver_user_id=st.ub.id, approver_record_id=r.id, order=p,
        )
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# handle_order_update_notifications
# =========================================================================== #

def _ou(db, st, etype, o, was_ready, actor=None, **kw):
    return ans.handle_order_update_notifications(
        db, workspace_id=st.w1.id, entity_type=etype, entity_id=o.id, actor_user_id=(actor or st.ua).id,
        order=o, was_ready=was_ready, **kw,
    )


def test_apn_ou_01__unconfirmed_reset_text(db, st):
    """APN-OU-01 — unconfirmed sections with approvers: the creator gets the reset text, nothing else.
    Rules: handle_order_update_notifications R1."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10)
    result = ans.handle_order_update_notifications(
        db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=p.id, actor_user_id=st.ua.id,
        order=p, was_ready=False, section_was_unconfirmed=True,
    )
    # Then 1
    assert result is None
    # Then 2
    assert recips(db) == [st.uc.id]
    # Then 3
    n = note(db, st.uc)
    assert n.notification_type == "section_confirm"
    assert n.source_type == "section"
    assert n.source_id == p.id
    assert n.actor_user_id == st.ua.id
    # Then 4
    assert note(db, st.uc).preview == "Approvals were reset — re-confirm sections before approving"


def test_apn_ou_02__unconfirmed_no_requirement_nothing(db, st):
    """APN-OU-02 — unconfirmed sections with no approvers required: nothing.
    Rules: handle_order_update_notifications R1, R4."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    result = _ou(db, st, "purchase_order", p, False, section_was_unconfirmed=True)
    # Then 1
    assert result is None
    # Then 2
    assert len(notes(db)) == 0


def test_apn_ou_03__ready_to_not_ready_gap_text(db, st):
    """APN-OU-03 — ready to not ready: the creator gets the gap text.
    Rules: handle_order_update_notifications R2."""
    p = po(db, st, "PO-1", supplier_confirmed=True)
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10)
    _ou(db, st, "purchase_order", p, True)
    # Then 1
    assert recips(db) == [st.uc.id]
    # Then 2
    n = note(db, st.uc)
    assert n.notification_type == "section_confirm"
    assert n.actor_user_id == st.ua.id
    assert n.preview == "Confirm Order details, Order items before approvals can proceed"


def test_apn_ou_04__ready_to_not_ready_no_requirement(db, st):
    """APN-OU-04 — ready to not ready with no approvers required: nothing.
    Rules: handle_order_update_notifications R2, R4."""
    p = po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    _ou(db, st, "purchase_order", p, True)
    # Then 1
    assert len(notes(db)) == 0


def test_apn_ou_05__ready_to_not_ready_suspended_creator(db, st):
    """APN-OU-05 — ready to not ready: a suspended creator gets nothing.
    Rules: handle_order_update_notifications R2."""
    p = po(db, st, "PO-1", created_by=st.us.id)
    poa(db, st, p, st.ub, 9)
    _ou(db, st, "purchase_order", p, True)
    # Then 1
    assert len(notes(db)) == 0


def test_apn_ou_06__became_ready_actor_included(db, st):
    """APN-OU-06 — not ready to ready: every pending approver, the actor included.
    Rules: handle_order_update_notifications R3, R4."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    poa(db, st, p, st.ud, 10)
    _ou(db, st, "purchase_order", p, False, actor=st.ub)
    # Then 1
    assert recips(db) == sorted([st.ub.id, st.ud.id])
    # Then 2
    assert len(to(db, st.uc)) == 0
    # Then 3
    n = note(db, st.ub)
    assert n.notification_type == "approval_pending"
    assert n.actor_user_id == st.ub.id
    assert n.preview == "0 of 2 approval(s) collected"
    # Then 4
    n = note(db, st.ud)
    assert n.notification_type == "approval_pending"
    assert n.source_type == "order"
    assert n.source_id == p.id


def test_apn_ou_07__became_ready_filters_recipients(db, st):
    """APN-OU-07 — not ready to ready: inactive and other-workspace approvers get nothing.
    Rules: handle_order_update_notifications R3."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.uz0, 8)
    poa(db, st, p, st.us, 9)
    poa(db, st, p, st.ub, 10)
    poa(db, st, p, st.uz2, 11)
    _ou(db, st, "purchase_order", p, False)
    # Then 1
    assert recips(db) == [st.ub.id]


def test_apn_ou_08__became_ready_transfer(db, st):
    """APN-OU-08 — not ready to ready on a transfer order.
    Rules: handle_order_update_notifications R3."""
    t = to_(db, st, "TO-1")
    to_line(db, st, t)
    toa(db, st, t, st.ub, 9)
    _ou(db, st, "transfer_order", t, False)
    # Then 1
    assert recips(db) == [st.ub.id]
    # Then 2
    n = note(db, st.ub)
    assert n.notification_type == "approval_pending"
    assert n.entity_type == "transfer_order"
    assert n.preview == "0 of 1 approval(s) collected"


def test_apn_ou_09__became_ready_no_requirement(db, st):
    """APN-OU-09 — not ready to ready with no approvers required: nothing.
    Rules: handle_order_update_notifications R3, R4."""
    p = ready_po(db, st, "PO-1", required_approvals=0)
    poa(db, st, p, st.ub, 9)
    _ou(db, st, "purchase_order", p, False)
    # Then 1
    assert len(notes(db)) == 0


def test_apn_ou_10__ready_stays_ready(db, st):
    """APN-OU-10 — ready stays ready: nothing.
    Rules: handle_order_update_notifications R4."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    _ou(db, st, "purchase_order", p, True)
    # Then 1
    assert len(notes(db)) == 0


def test_apn_ou_11__not_ready_stays_not_ready(db, st):
    """APN-OU-11 — not ready stays not ready: nothing.
    Rules: handle_order_update_notifications R4."""
    p = po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    _ou(db, st, "purchase_order", p, False)
    # Then 1
    assert len(notes(db)) == 0


def test_apn_ou_12__unknown_order_404(db, st):
    """APN-OU-12 — an unknown order id raises 404 even when nothing would be sent.
    Rules: handle_order_update_notifications R5."""
    p = ready_po(db, st, "PO-1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ans.handle_order_update_notifications(
            db, workspace_id=st.w1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=st.ua.id,
            order=p, was_ready=True,
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order with ID 999999999 not found"
    # Then 3
    assert len(notes(db)) == 0


def test_apn_ou_13__no_commit(db, st):
    """APN-OU-13 — writes but never commits or rolls back.
    Rules: handle_order_update_notifications R3 (no commit; spec Overview)."""
    p = ready_po(db, st, "PO-1")
    poa(db, st, p, st.ub, 9)
    db.commit()
    c, r = spies(db)
    with c as cm, r as rb:
        _ou(db, st, "purchase_order", p, False)
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    db.rollback()
    assert len(notes(db)) == 0


# =========================================================================== #
# detect_section_unconfirmed
# =========================================================================== #

def _sn(s, d, i, inv):
    return SimpleNamespace(supplier_confirmed=s, details_confirmed=d, items_confirmed=i, invoice_confirmed=inv)


@pytest.mark.parametrize(
    ("order", "update", "expected"),
    [
        pytest.param(_sn(False, False, True, False), {"items_confirmed": 0}, True, id="APN-DS-01"),
        pytest.param(_sn(False, False, False, True), {"invoice_confirmed": False}, True, id="APN-DS-02"),
        pytest.param(_sn(True, False, False, False), {"supplier_confirmed": None}, True, id="APN-DS-03"),
        pytest.param(_sn(False, True, False, False), {"details_confirmed": ""}, True, id="APN-DS-04"),
        pytest.param(_sn(True, True, True, False), {"invoice_confirmed": False}, False, id="APN-DS-05"),
        pytest.param(_sn(True, True, True, True), {"items_confirmed": True, "supplier_confirmed": 1}, False,
                     id="APN-DS-06"),
        pytest.param(_sn(True, True, True, True), {"notes": ""}, False, id="APN-DS-07"),
    ],
)
def test_apn_ds_01_07__po_section_turned_off(order, update, expected):
    """APN-DS-01 … DS-07 — a falsy new value on a confirmed section counts; off, truthy or absent does not.
    Rules: detect_section_unconfirmed R1, R2."""
    result = ans.detect_section_unconfirmed("purchase_order", order, update)
    # Then 1
    assert result is expected


def test_apn_ds_08__other_type_false():
    """APN-DS-08 — any other type is false and the order is not read.
    Rules: detect_section_unconfirmed R3."""
    result = ans.detect_section_unconfirmed("transfer_order", None, {"supplier_confirmed": False})
    # Then 1
    assert result is False


def test_apn_ds_09__missing_confirm_attribute_counts_as_off():
    """APN-DS-09 — an order without the confirm attribute counts it as off.
    Rules: detect_section_unconfirmed R2a."""
    order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True)
    result = ans.detect_section_unconfirmed("purchase_order", order, {"invoice_confirmed": False})
    # Then 1
    assert result is False


# =========================================================================== #
# Sales readiness (delegation, final)
# =========================================================================== #

@BUG_1205
def test_apn_sr_01__sales_ready(db, st):
    """APN-SR-01 — sales order with order info and items confirmed is ready.
    Rules: _is_approval_ready R6a [BUG-1205]."""
    order = SimpleNamespace(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=False)
    result = ans._is_approval_ready(db, "sales_order", order, st.w1.id)
    # Then 1
    assert result is True


def test_apn_sr_02__sales_items_missing_not_ready(db, st):
    """APN-SR-02 — sales order without items confirmed is not ready.
    Rules: _is_approval_ready R6a."""
    order = SimpleNamespace(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=True)
    result = ans._is_approval_ready(db, "sales_order", order, st.w1.id)
    # Then 1
    assert result is False


@BUG_1205
def test_apn_sr_03__sales_gap_both(db, st):
    """APN-SR-03 — sales gap text lists both missing sections.
    Rules: _section_gap_preview R6a [BUG-1205]."""
    order = SimpleNamespace(order_info_confirmed=False, items_confirmed=False, invoice_confirmed=False)
    result = ans._section_gap_preview(db, "sales_order", order)
    # Then 1
    assert result == "Confirm Order info, Order items before approvals can proceed"


@BUG_1205
def test_apn_sr_04__sales_gap_one(db, st):
    """APN-SR-04 — sales gap text lists only the missing one.
    Rules: _section_gap_preview R6a [BUG-1205]."""
    order = SimpleNamespace(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=False)
    result = ans._section_gap_preview(db, "sales_order", order)
    # Then 1
    assert result == "Confirm Order items before approvals can proceed"


@BUG_1205
def test_apn_sr_05__sales_fully_confirmed(db, st):
    """APN-SR-05 — sales order fully confirmed: the invoice is not listed.
    Rules: _section_gap_preview R6a [BUG-1205]."""
    order = SimpleNamespace(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=False)
    result = ans._section_gap_preview(db, "sales_order", order)
    # Then 1
    assert result == "Complete remaining sections before approvals can proceed"
