"""Unit tests for app/managers/expense_order_manager.py.

Implements tests/unit/managers/expense_order_manager.cases.md (revision 4), one
test per case. Real Postgres session (`db` fixture). Mocks: the spec's two
listed utcnow targets (every test, autouse) plus SQL-capture listeners for the
HR-10 row-lock xfail cases. Nothing else is mocked.
"""
# ruff: noqa: SIM117, DTZ001, DTZ005, DTZ011, FURB157  (prescribed by the cards: nested with, naive datetimes, Decimal("...") literals)
import itertools
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.managers.expense_order_manager import ExpenseOrderManager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.department import Department
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.factory import Factory
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.profile import Profile
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderFromTemplateCreate,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "T0" / "NOW" (both naive)
T0 = datetime(2026, 1, 1, 9, 0, 0)
NOW = datetime(2026, 3, 11, 10, 0, 0)  # Wednesday

BUG_004 = "BUG-004: blank/whitespace description accepted on update"
BUG_021 = "BUG-021: item schemas accept more than 2 decimals / 13 integer digits"
BUG_340 = "BUG-340: a soft-deleted factory/department is accepted as cost center"
BUG_362 = "BUG-362: item schemas accept quantity <= 0 or negative unit_price"
BUG_740 = "BUG-740: updated_by and approvals-reset/item_updated fire even when nothing changed"
BUG_741 = "BUG-741: update_expense_order does not lock the order row (HR-10)"
BUG_742 = "BUG-742: delete_expense_order does not lock the order row or check for a linked invoice"
BUG_743 = "BUG-743: add_item/update_item/remove_item do not lock the parent order row (HR-10)"
BUG_744 = "BUG-744: set_approval does not lock the order row (HR-10)"
BUG_745 = "BUG-745: hub search text is not escaped for ILIKE wildcards/backslash"
BUG_746 = "BUG-746: recent-orders list sorts never-updated orders before recently-updated ones"
BUG_747 = "BUG-747: financial snapshot open-by-account ties have no fixed order"
BUG_748 = "BUG-748: financial snapshot unpaid-pipeline sample ties have no fixed order"
BUG_749 = "BUG-749: expense number generation is globally unique, text-sorted and not race-safe"
BUG_750 = "BUG-750: account_id / order_template_id accepted without a workspace/liveness check"
BUG_751 = "BUG-751: invoice_id and line approved are client-writable internal fields"
BUG_752 = "BUG-752: category 'other' keeps a stale cost_center_id"
BUG_753 = "BUG-753: explicit null cannot clear optional order/line fields"
BUG_754 = "BUG-754: voided orders can still be edited and approved"
BUG_755 = "BUG-755: an order with no approvers and no explicit requirement counts as approved"
BUG_756 = "BUG-756: approvers can be added/removed on a completed order"
BUG_757 = "BUG-757: re-approving or withdrawing a no-op state is recorded again"
BUG_758 = "BUG-758: line-level readiness gap has no specific reason text"
BUG_759 = "BUG-759: create_expense_order_from_template fails when the default approver is inactive"
BUG_1193 = "BUG-1193: a deleted expense order leaves no record of itself or of who deleted it"


# Convention "Externals": every test patches both utcnow targets to NOW
@pytest.fixture(autouse=True)
def _utcnow():
    with patch("app.managers.expense_order_manager.utcnow", return_value=NOW), \
         patch("app.dao.expense_order.utcnow", return_value=NOW):
        yield


@pytest.fixture
def M():
    return ExpenseOrderManager()


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


def _member(db, ws, profile, *, position=None, status="active"):
    row = WorkspaceMember(
        workspace_id=ws.id, user_id=profile.id, role="ground-team",
        position=position, status=status,
    )
    db.add(row)
    db.flush()
    return row


def member_of(db, ws, user):
    db.expire_all()
    return db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user.id
        )
    ).scalar_one()


# Convention "Profiles": U1 "Abid Hasan", U2 "Karim Ali", U3 "Rahim Uddin", U4 "Nadia Khan"
# Convention "Memberships": U1, U2, U3 active members of W1 (U2 "Accountant"); U4 active
# member of W2 only.
@pytest.fixture
def u1(db, w1):
    p = make_profile(db, name="Abid Hasan")
    _member(db, w1, p)
    return p


@pytest.fixture
def u2(db, w1):
    p = make_profile(db, name="Karim Ali")
    _member(db, w1, p, position="Accountant")
    return p


@pytest.fixture
def u3(db, w1):
    p = make_profile(db, name="Rahim Uddin")
    _member(db, w1, p)
    return p


@pytest.fixture
def u4(db, w2):
    p = make_profile(db, name="Nadia Khan")
    _member(db, w2, p)
    return p


@pytest.fixture
def u5(db):
    """A profile with no membership anywhere."""
    return make_profile(db, name="New Guy")


# Convention reference rows: factories/departments/accounts, created only when requested.
@pytest.fixture
def f1(db, w1, u1):
    row = Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1", is_active=True, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f3(db, w1, u1):
    """A second live factory of W1 (distinct from F1)."""
    row = Factory(workspace_id=w1.id, name="Factory Three", abbreviation="F3", is_active=True, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def fi(db, w1, u1):
    row = Factory(workspace_id=w1.id, name="Factory Inactive", abbreviation="FI", is_active=False, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def fd(db, w1, u1):
    row = Factory(workspace_id=w1.id, name="Factory Deleted", abbreviation="FD", is_active=True, is_deleted=True, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f2(db, w2, u4):
    row = Factory(workspace_id=w2.id, name="Factory Two", abbreviation="F2", is_active=True, is_deleted=False, created_by=u4.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def d1(db, w1, u1):
    row = Department(workspace_id=w1.id, name="Department One", is_active=True, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def di(db, w1, u1):
    row = Department(workspace_id=w1.id, name="Department Inactive", is_active=False, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def dd(db, w1, u1):
    row = Department(workspace_id=w1.id, name="Department Deleted", is_active=True, is_deleted=True, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def d2(db, w2, u4):
    row = Department(workspace_id=w2.id, name="Department Two", is_active=True, is_deleted=False, created_by=u4.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def a1(db, w1, u1):
    row = Account(workspace_id=w1.id, name="Acme Supplies", is_active=True, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def a2(db, w1, u1):
    row = Account(workspace_id=w1.id, name="Beta Traders", is_active=True, is_deleted=False, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def ax(db, w1, u1):
    row = Account(workspace_id=w1.id, name="Old Vendor", is_active=True, is_deleted=True, created_by=u1.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def aw2(db, w2, u4):
    row = Account(workspace_id=w2.id, name="Acme West", is_active=True, is_deleted=False, created_by=u4.id)
    db.add(row)
    db.flush()
    return row


# Convention "Order rows inserted directly": one insert + flush per row.
# Per the spec's Defaults, expense_category="factory" with cost_center_id=F1
# unless the test overrides either (no FK on cost_center_id, so this is safe
# to default even for a W2 order -- no test relies on it there).
@pytest.fixture
def order_factory(db, f1):
    counters = {}

    def _mk(ws, created_by, **over):
        if ws.id not in counters:
            start = 101 if not counters else 901
            counters[ws.id] = itertools.count(start)
        n = next(counters[ws.id])
        defaults = dict(
            workspace_id=ws.id,
            expense_number=f"EXP-2000-{n}",
            expense_category="factory",
            cost_center_id=f1.id,
            account_id=None,
            expense_date=date(2026, 3, 1),
            due_date=None,
            description="Rent",
            required_approvals=None,
            invoice_id=None,
            voided=False,
            completed_at=None,
            subtotal=Decimal("0"),
            total_amount=Decimal("0"),
            created_by=created_by.id if hasattr(created_by, "id") else created_by,
            updated_by=None,
            created_at=T0,
            updated_at=None,
        )
        defaults.update(over)
        row = ExpenseOrder(**defaults)
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def line_factory(db):
    def _mk(order, line_number, **over):
        defaults = dict(
            workspace_id=order.workspace_id,
            expense_order_id=order.id,
            line_number=line_number,
            description=f"Line {line_number}",
            quantity=Decimal("1"),
            unit=None,
            unit_price=Decimal("10.00"),
            line_subtotal=Decimal("10.00"),
            notes=None,
        )
        defaults.update(over)
        row = ExpenseOrderItem(**defaults)
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def approver_factory(db):
    def _mk(order, user, *, assigned_by, approved=False, approved_at=None, assigned_at=T0, workspace_id=None):
        row = ExpenseOrderApprover(
            workspace_id=workspace_id if workspace_id is not None else order.workspace_id,
            expense_order_id=order.id,
            user_id=user.id if hasattr(user, "id") else user,
            assigned_by=assigned_by.id if hasattr(assigned_by, "id") else assigned_by,
            assigned_at=assigned_at,
            approved=approved,
            approved_at=approved_at,
        )
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def event_factory(db):
    def _mk(order, event_type, description, *, performed_by=None, metadata=None, created_at=T0, workspace_id=None):
        row = ExpenseOrderEvent(
            workspace_id=workspace_id if workspace_id is not None else order.workspace_id,
            expense_order_id=order.id,
            event_type=event_type,
            description=description,
            metadata_json=metadata,
            performed_by=performed_by.id if hasattr(performed_by, "id") else performed_by,
            created_at=created_at,
        )
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def invoice_factory(db):
    def _mk(ws, account, *, invoice_status="draft", payment_status="unpaid",
            invoice_amount=Decimal("0"), paid_amount=Decimal("0"), order_id=None):
        row = AccountInvoice(
            workspace_id=ws.id, account_id=account.id, order_type="expense_order", order_id=order_id,
            invoice_type="payable", invoice_status=invoice_status, invoice_amount=invoice_amount,
            paid_amount=paid_amount, invoice_date=date(2026, 3, 1), payment_status=payment_status,
        )
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def template_factory(db):
    def _mk(ws, **over):
        defaults = dict(
            workspace_id=ws.id, template_name="Monthly rent", description="Rent for the plant",
            expense_category="factory", cost_center_id=None, account_id=None,
            is_active=True, requires_approval=True, auto_approve=False, default_approver_id=None,
        )
        defaults.update(over)
        row = OrderTemplate(**defaults)
        db.add(row)
        db.flush()
        return row

    return _mk


@pytest.fixture
def template_item_factory(db):
    def _mk(tpl, line_number, **over):
        defaults = dict(
            workspace_id=tpl.workspace_id, order_template_id=tpl.id, line_number=line_number,
            description=f"Line {line_number}", quantity=Decimal("1"), unit=None,
            unit_price=Decimal("10.00"), notes=None,
        )
        defaults.update(over)
        row = OrderTemplateItem(**defaults)
        db.add(row)
        db.flush()
        return row

    return _mk


def ready_order(order_factory, line_factory, ws, created_by, **over):
    """R = default order plus one line: 1 'Rent' qty 1 price 100.00; totals 100.00."""
    o = order_factory(ws, created_by, subtotal=Decimal("100.00"), total_amount=Decimal("100.00"), **over)
    line_factory(o, 1, description="Rent", quantity=Decimal("1"), unit_price=Decimal("100.00"), line_subtotal=Decimal("100.00"))
    return o


@pytest.fixture
def R(order_factory, line_factory, w1, u1, f1):
    """Convention 'R' (ready order), bound to W1 / U1 unless a test overrides fields.

    Per the spec's generic order Defaults, cost_center_id defaults to F1 (category
    stays 'factory') so R is approval-ready out of the box; override explicitly
    for cases that need a different category/cost center.
    """
    def _mk(**over):
        over.setdefault("cost_center_id", f1.id)
        return ready_order(order_factory, line_factory, w1, u1, **over)
    return _mk


@pytest.fixture
def O(order_factory, w1, u1):
    """Shorthand for a plain default order of W1 created by U1."""
    def _mk(**over):
        return order_factory(w1, u1, **over)
    return _mk


@pytest.fixture
def O5(order_factory, w2, u4):
    """Convention 'O5' -- a default order of W2 created by U4."""
    return order_factory(w2, u4, cost_center_id=None)


# --------------------------------------------------------------------------- #
# Generic re-read / snapshot helpers
# --------------------------------------------------------------------------- #

ORDER_COLS = (
    "workspace_id", "expense_number", "order_template_id", "account_id", "expense_category",
    "cost_center_id", "expense_date", "due_date", "subtotal", "total_amount", "required_approvals",
    "invoice_id", "voided", "void_note", "voided_at", "voided_by", "description", "created_by",
    "created_at", "updated_by", "completed_at",
)


def reread_order(db, order_id):
    db.expire_all()
    return db.get(ExpenseOrder, order_id)


def order_snap(db, order_id):
    o = reread_order(db, order_id)
    return {c: getattr(o, c) for c in ORDER_COLS}


def reread_item(db, item_id):
    db.expire_all()
    return db.get(ExpenseOrderItem, item_id)


def reread_approver(db, approver_id):
    db.expire_all()
    return db.get(ExpenseOrderApprover, approver_id)


def reread_event(db, event_id):
    db.expire_all()
    return db.get(ExpenseOrderEvent, event_id)


def events_of(db, order_id):
    db.expire_all()
    return db.scalars(
        select(ExpenseOrderEvent).where(ExpenseOrderEvent.expense_order_id == order_id).order_by(ExpenseOrderEvent.id)
    ).all()


def approvers_of(db, order_id):
    db.expire_all()
    return db.scalars(
        select(ExpenseOrderApprover).where(ExpenseOrderApprover.expense_order_id == order_id).order_by(ExpenseOrderApprover.id)
    ).all()


def lines_of(db, order_id):
    db.expire_all()
    return db.scalars(
        select(ExpenseOrderItem).where(ExpenseOrderItem.expense_order_id == order_id).order_by(ExpenseOrderItem.line_number)
    ).all()


def approver_row(db, order_id, user_id):
    db.expire_all()
    return db.execute(
        select(ExpenseOrderApprover).where(
            ExpenseOrderApprover.expense_order_id == order_id, ExpenseOrderApprover.user_id == user_id
        )
    ).scalar_one_or_none()


def ws_counts(db, ws_id):
    """(#orders, #lines, #approvers, #events) in this workspace."""
    db.expire_all()
    return (
        db.scalar(select(func.count()).select_from(ExpenseOrder).where(ExpenseOrder.workspace_id == ws_id)),
        db.scalar(select(func.count()).select_from(ExpenseOrderItem).where(ExpenseOrderItem.workspace_id == ws_id)),
        db.scalar(select(func.count()).select_from(ExpenseOrderApprover).where(ExpenseOrderApprover.workspace_id == ws_id)),
        db.scalar(select(func.count()).select_from(ExpenseOrderEvent).where(ExpenseOrderEvent.workspace_id == ws_id)),
    )


def missing_id(db, Model):
    return (db.scalar(select(func.max(Model.id))) or 0) + 1000


def not_found_order(eo_id):
    return f"Expense order with ID {eo_id} not found"


def E(event_type, description):
    return (event_type, description)


def events_as_pairs(evs):
    return [(e.event_type, e.description) for e in evs]


# Convention "SQL capture": a before_cursor_execute listener recording statements run
# during the action only.
class SQLCapture:
    def __init__(self, engine):
        self.engine = engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    @property
    def locked(self):
        return any(
            "expense_orders" in s and "FOR UPDATE" in s.upper() for s in self.statements
        )


def real_window():
    """A (before, after) pair of real-clock utcnow() readings around an action."""
    from app.utils.time import utcnow as real_utcnow
    return real_utcnow


def mutate(db, obj, **attrs):
    """Set attributes a NOT NULL column would refuse, without flushing.

    Convention: readiness cases set an attribute on the loaded object inside
    session.no_autoflush (the harness session has autoflush=False anyway, so
    this never triggers a write; it documents intent per the spec's note).
    """
    with db.no_autoflush:
        for k, v in attrs.items():
            setattr(obj, k, v)
    return obj


# --------------------------------------------------------------------------- #
# `_has_recorded_approvals`
# --------------------------------------------------------------------------- #

def test_eo_hra_01__true_when_one_approved(db, M, w1, O, u1, u2, approver_factory):
    """EO-HRA-01 — at least one approved row -> True.
    Rules: _has_recorded_approvals R1."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=False)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    assert M._has_recorded_approvals(db, o.id, w1.id) is True


def test_eo_hra_02__false_when_all_pending(db, M, w1, O, u1, u2, approver_factory):
    """EO-HRA-02 — all approvers pending -> False.
    Rules: _has_recorded_approvals R2."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=False)
    approver_factory(o, u2, assigned_by=u1, approved=False)
    assert M._has_recorded_approvals(db, o.id, w1.id) is False


def test_eo_hra_03__false_when_no_approvers(db, M, w1, O):
    """EO-HRA-03 — no approver rows -> False.
    Rules: _has_recorded_approvals R2."""
    o = O()
    assert M._has_recorded_approvals(db, o.id, w1.id) is False


def test_eo_hra_04__other_workspace_approver_ignored(db, M, w1, w2, O, u1, u4, approver_factory):
    """EO-HRA-04 — an approver row stored under another workspace is ignored.
    Rules: _has_recorded_approvals R3."""
    o = O()
    approver_factory(o, u4, assigned_by=u1, approved=True, approved_at=T0, workspace_id=w2.id)
    assert M._has_recorded_approvals(db, o.id, w1.id) is False


def test_eo_hra_05__other_orders_approval_does_not_count(db, M, w1, O, u1, u2, approver_factory):
    """EO-HRA-05 — another order's approval does not count for this order.
    Rules: _has_recorded_approvals R1."""
    o = O()
    p = O()
    approver_factory(p, u2, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u1, assigned_by=u1, approved=False)
    assert M._has_recorded_approvals(db, o.id, w1.id) is False


# --------------------------------------------------------------------------- #
# `is_approvable`
# --------------------------------------------------------------------------- #

def test_eo_ia_01__ready_order_is_approvable(db, M, R):
    """EO-IA-01 — a fully ready order is approvable.
    Rules: is_approvable R6."""
    r = R()
    assert M.is_approvable(db, r) is True


def test_eo_ia_02__blank_category(db, M, R):
    """EO-IA-02 — expense_category='' -> False.
    Rules: is_approvable R1."""
    r = R(expense_category="")
    assert M.is_approvable(db, r) is False


def test_eo_ia_03__none_category(db, M, R):
    """EO-IA-03 — expense_category=None -> False.
    Rules: is_approvable R1."""
    r = R()
    mutate(db, r, expense_category=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_04__none_expense_date(db, M, R):
    """EO-IA-04 — expense_date=None -> False.
    Rules: is_approvable R1."""
    r = R()
    mutate(db, r, expense_date=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_05__factory_no_cost_center(db, M, R):
    """EO-IA-05 — category factory, cost_center_id=None -> False.
    Rules: is_approvable R2."""
    r = R(cost_center_id=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_06__department_no_cost_center(db, M, R):
    """EO-IA-06 — category department, cost_center_id=None -> False.
    Rules: is_approvable R2."""
    r = R(expense_category="department", cost_center_id=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_07__other_no_cost_center_ok(db, M, R):
    """EO-IA-07 — category other needs no cost center -> True.
    Rules: is_approvable R2, R6."""
    r = R(expense_category="other", cost_center_id=None)
    assert M.is_approvable(db, r) is True


def test_eo_ia_08__none_description(db, M, R):
    """EO-IA-08 — description=None -> False.
    Rules: is_approvable R3."""
    r = R()
    mutate(db, r, description=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_09__empty_description(db, M, R):
    """EO-IA-09 — description='' -> False.
    Rules: is_approvable R3."""
    r = R(description="")
    assert M.is_approvable(db, r) is False


def test_eo_ia_10__whitespace_description(db, M, R):
    """EO-IA-10 — description='   ' -> False.
    Rules: is_approvable R3."""
    r = R(description="   ")
    assert M.is_approvable(db, r) is False


def test_eo_ia_11__single_char_description(db, M, R):
    """EO-IA-11 — description='a' -> True.
    Rules: is_approvable R3."""
    r = R(description="a")
    assert M.is_approvable(db, r) is True


def test_eo_ia_12__no_lines(db, M, O):
    """EO-IA-12 — default order with no lines -> False.
    Rules: is_approvable R4."""
    o = O()
    assert M.is_approvable(db, o) is False


def test_eo_ia_13__line_whitespace_description(db, M, R, line_factory):
    """EO-IA-13 — a line with whitespace-only description -> False.
    Rules: is_approvable R5."""
    r = R()
    line_factory(r, 2, description="  ", quantity=Decimal("1"))
    assert M.is_approvable(db, r) is False


def test_eo_ia_14__line_none_description(db, M, R, line_factory):
    """EO-IA-14 — a line with description=None -> False.
    Rules: is_approvable R5."""
    r = R()
    line_factory(r, 2, description=None, quantity=Decimal("1"))
    assert M.is_approvable(db, r) is False


def test_eo_ia_15__line_zero_quantity(db, M, R, line_factory):
    """EO-IA-15 — a line with quantity=0 -> False.
    Rules: is_approvable R5."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("0"))
    assert M.is_approvable(db, r) is False


def test_eo_ia_16__line_negative_quantity(db, M, R, line_factory):
    """EO-IA-16 — a line with quantity=-5 -> False.
    Rules: is_approvable R5."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("-5"))
    assert M.is_approvable(db, r) is False


def test_eo_ia_17__line_none_quantity(db, M, R, line_factory):
    """EO-IA-17 — a line with quantity=None counts as 0 -> False.
    Rules: is_approvable R5."""
    r = R()
    line = line_factory(r, 2, description="Water")
    mutate(db, line, quantity=None)
    assert M.is_approvable(db, r) is False


def test_eo_ia_18__line_boundary_quantity(db, M, R, line_factory):
    """EO-IA-18 — a line with quantity=0.01 -> True.
    Rules: is_approvable R5, R6."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("0.01"))
    assert M.is_approvable(db, r) is True


def test_eo_ia_19__unit_price_not_checked(db, M, R, line_factory):
    """EO-IA-19 — unit_price 0 / None / negative never blocks readiness -> True.
    Rules: is_approvable R6."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("1"), unit_price=Decimal("0"))
    line_factory(r, 3, description="Water", quantity=Decimal("1"), unit_price=None)
    line_factory(r, 4, description="Water", quantity=Decimal("1"), unit_price=Decimal("-100.00"))
    assert M.is_approvable(db, r) is True


def test_eo_ia_20__lines_isolated_by_workspace(db, M, O, w2, line_factory):
    """EO-IA-20 — R has no lines of its own; a foreign-workspace line for its id
    does not count -> False (lines loaded by id and workspace).
    Rules: is_approvable R4."""
    o = O()  # same readiness fields as R, but no lines of its own
    line_factory(o, 1, workspace_id=w2.id)
    assert M.is_approvable(db, o) is False


# --------------------------------------------------------------------------- #
# `approvability_gap_reason`
# --------------------------------------------------------------------------- #

CAT_DATE_MSG = "Set category and expense date before approvals can proceed"
DESC_MSG = "Add a description before approvals can proceed"
NO_LINES_MSG = "Add at least one expense line before approvals can proceed"


def test_eo_gr_01__ready_order_has_no_gap(db, M, R):
    """EO-GR-01 — a fully ready order -> None.
    Rules: approvability_gap_reason R5."""
    r = R()
    assert M.approvability_gap_reason(db, r) is None


def test_eo_gr_02__blank_category(db, M, R):
    """EO-GR-02 — expense_category='' -> category/date message.
    Rules: approvability_gap_reason R1."""
    r = R(expense_category="")
    assert M.approvability_gap_reason(db, r) == CAT_DATE_MSG


def test_eo_gr_03__none_expense_date(db, M, R):
    """EO-GR-03 — expense_date=None -> category/date message.
    Rules: approvability_gap_reason R1."""
    r = R()
    mutate(db, r, expense_date=None)
    assert M.approvability_gap_reason(db, r) == CAT_DATE_MSG


def test_eo_gr_04__factory_no_cost_center(db, M, R):
    """EO-GR-04 — factory with no cost center -> factory message.
    Rules: approvability_gap_reason R2."""
    r = R(cost_center_id=None)
    assert M.approvability_gap_reason(db, r) == "Select a factory for this expense order before approvals can proceed"


def test_eo_gr_05__department_no_cost_center(db, M, R):
    """EO-GR-05 — department with no cost center -> department message.
    Rules: approvability_gap_reason R2."""
    r = R(expense_category="department", cost_center_id=None)
    assert M.approvability_gap_reason(db, r) == "Select a department for this expense order before approvals can proceed"


def test_eo_gr_06__other_no_cost_center_ok(db, M, R):
    """EO-GR-06 — other needs no cost center -> None.
    Rules: approvability_gap_reason R2."""
    r = R(expense_category="other", cost_center_id=None)
    assert M.approvability_gap_reason(db, r) is None


def test_eo_gr_07__whitespace_description(db, M, R):
    """EO-GR-07 — description='   ' -> description message.
    Rules: approvability_gap_reason R3."""
    r = R(description="   ")
    assert M.approvability_gap_reason(db, r) == DESC_MSG


def test_eo_gr_08__none_description(db, M, R):
    """EO-GR-08 — description=None -> description message.
    Rules: approvability_gap_reason R3."""
    r = R()
    mutate(db, r, description=None)
    assert M.approvability_gap_reason(db, r) == DESC_MSG


def test_eo_gr_09__no_lines(db, M, O):
    """EO-GR-09 — default order with no lines -> no-lines message.
    Rules: approvability_gap_reason R4."""
    o = O()
    assert M.approvability_gap_reason(db, o) == NO_LINES_MSG


def test_eo_gr_10__category_date_wins_first(db, M, O, f1):
    """EO-GR-10 — category/date check wins over cost center, description, lines.
    Rules: approvability_gap_reason R1 before R2, R3."""
    o = O(expense_category="factory", cost_center_id=None, description=None)
    mutate(db, o, expense_date=None)
    assert M.approvability_gap_reason(db, o) == CAT_DATE_MSG


def test_eo_gr_11__cost_center_wins_over_description_and_lines(db, M, O):
    """EO-GR-11 — cost-center check wins over description and lines.
    Rules: approvability_gap_reason R2 before R3, R4."""
    o = O(expense_category="factory", cost_center_id=None, description="")
    assert M.approvability_gap_reason(db, o) == "Select a factory for this expense order before approvals can proceed"


def test_eo_gr_12__description_wins_over_lines(db, M, O, f1):
    """EO-GR-12 — description check wins over the no-lines check.
    Rules: approvability_gap_reason R3 before R4."""
    o = O(cost_center_id=f1.id)
    mutate(db, o, description=None)
    assert M.approvability_gap_reason(db, o) == DESC_MSG


@pytest.mark.xfail(strict=True, reason=BUG_758 + " — fails today on: returns None")
def test_eo_gr_13__bug_758_blank_line_description_hidden(db, M, R, line_factory):
    """EO-GR-13 — a line with a blank description should name the line problem.
    Rules: approvability_gap_reason R6 [BUG-758]."""
    r = R()
    line_factory(r, 2, description="  ")
    assert M.approvability_gap_reason(db, r) == (
        "Every expense line needs a description and a quantity above 0 before approvals can proceed"
    )


@pytest.mark.xfail(strict=True, reason=BUG_758 + " — fails today on: returns None")
def test_eo_gr_14__bug_758_zero_qty_line_hidden(db, M, R, line_factory):
    """EO-GR-14 — a line with quantity=0 should name the line problem.
    Rules: approvability_gap_reason R6 [BUG-758]."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("0"))
    assert M.approvability_gap_reason(db, r) == (
        "Every expense line needs a description and a quantity above 0 before approvals can proceed"
    )


def test_eo_gr_15__line_boundary_qty_no_price_ok(db, M, R, line_factory):
    """EO-GR-15 — a line with quantity=0.01, unit_price=None -> None.
    Rules: approvability_gap_reason R5."""
    r = R()
    line_factory(r, 2, description="Water", quantity=Decimal("0.01"), unit_price=None)
    assert M.approvability_gap_reason(db, r) is None


# --------------------------------------------------------------------------- #
# `_validate_order_allocation`
# --------------------------------------------------------------------------- #

def invalid_category_msg(value):
    return f"Invalid category: {value}. Must be factory, department, or other."


def test_eo_va_01__factory_happy(db, M, w1, f1):
    """EO-VA-01 — a live factory of this workspace -> None.
    Rules: _validate_order_allocation R4."""
    assert M._validate_order_allocation(db, w1.id, "factory", f1.id) is None


def test_eo_va_02__department_happy(db, M, w1, d1):
    """EO-VA-02 — a live department of this workspace -> None.
    Rules: _validate_order_allocation R6."""
    assert M._validate_order_allocation(db, w1.id, "department", d1.id) is None


def test_eo_va_03__wrong_case_category(db, M, w1, f1):
    """EO-VA-03 — 'Factory' is not a valid category -> 400.
    Rules: _validate_order_allocation R1 / Errors R1."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "Factory", f1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg("Factory")


def test_eo_va_04__leading_space_category(db, M, w1):
    """EO-VA-04 — a leading space in the category is not trimmed -> 400.
    Rules: _validate_order_allocation R1."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, " factory", None)
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg(" factory")


def test_eo_va_05__blank_category(db, M, w1):
    """EO-VA-05 — '' is not a valid category -> 400.
    Rules: _validate_order_allocation R1."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "", None)
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg("")


def test_eo_va_06__other_no_cost_center(db, M, w1):
    """EO-VA-06 — category other with cost_center_id=None -> None.
    Rules: _validate_order_allocation R2."""
    assert M._validate_order_allocation(db, w1.id, "other", None) is None


def test_eo_va_07__other_ignores_cost_center_value(db, M, w1):
    """EO-VA-07 — category other with an unrelated id -> no lookup, no error.
    Rules: _validate_order_allocation R2."""
    assert M._validate_order_allocation(db, w1.id, "other", 987654) is None


def test_eo_va_08__factory_missing_cost_center(db, M, w1):
    """EO-VA-08 — category factory, cost_center_id=None -> 400.
    Rules: _validate_order_allocation R3 / Errors R3."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "factory", None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this expense order"


def test_eo_va_09__department_missing_cost_center(db, M, w1):
    """EO-VA-09 — category department, cost_center_id=None -> 400.
    Rules: _validate_order_allocation R3 / Errors R3."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "department", None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a department for this expense order"


def test_eo_va_10__factory_not_found(db, M, w1):
    """EO-VA-10 — a non-existent factory id -> 404.
    Rules: _validate_order_allocation R4 / Errors R4."""
    missing = missing_id(db, Factory)
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "factory", missing)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"


def test_eo_va_11__factory_other_workspace(db, M, w1, f2):
    """EO-VA-11 — a factory of another workspace -> 404.
    Rules: _validate_order_allocation R4 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "factory", f2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"


@pytest.mark.xfail(strict=True, reason=BUG_340 + " — fails today on: no exception raised")
def test_eo_va_12__bug_340_soft_deleted_factory_rejected(db, M, w1, fd):
    """EO-VA-12 — a soft-deleted factory of this workspace -> 404.
    Rules: _validate_order_allocation R5 [BUG-340]."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "factory", fd.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"


def test_eo_va_13__inactive_live_factory_accepted(db, M, w1, fi):
    """EO-VA-13 — an inactive but live factory still counts as found.
    Rules: _validate_order_allocation R5."""
    assert M._validate_order_allocation(db, w1.id, "factory", fi.id) is None


def test_eo_va_14__department_not_found(db, M, w1):
    """EO-VA-14 — a non-existent department id -> 404.
    Rules: _validate_order_allocation R6 / Errors R6."""
    missing = missing_id(db, Department)
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "department", missing)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"


def test_eo_va_15__department_other_workspace(db, M, w1, d2):
    """EO-VA-15 — a department of another workspace -> 404.
    Rules: _validate_order_allocation R6 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "department", d2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"


@pytest.mark.xfail(strict=True, reason=BUG_340 + " — fails today on: no exception raised")
def test_eo_va_16__bug_340_soft_deleted_department_rejected(db, M, w1, dd):
    """EO-VA-16 — a soft-deleted department of this workspace -> 404.
    Rules: _validate_order_allocation R6 [BUG-340]."""
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "department", dd.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"


def test_eo_va_17__inactive_live_department_accepted(db, M, w1, di):
    """EO-VA-17 — an inactive but live department still counts as found.
    Rules: _validate_order_allocation R6."""
    assert M._validate_order_allocation(db, w1.id, "department", di.id) is None


def test_eo_va_18__zero_is_a_given_id_not_missing(db, M, w1):
    """EO-VA-18 — cost_center_id=0 is looked up, not treated as missing.
    Rules: _validate_order_allocation R7."""
    assert db.get(Factory, 0) is None
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "factory", 0)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"


def test_eo_va_19__factory_id_not_accepted_as_department(db, M, w1, f1):
    """EO-VA-19 — a factory's id is not accepted as a department id.
    Rules: _validate_order_allocation R4 (isolation)."""
    assert db.get(Department, f1.id) is None
    with pytest.raises(HTTPException) as exc:
        M._validate_order_allocation(db, w1.id, "department", f1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"


# --------------------------------------------------------------------------- #
# `resolve_invoice_account_id`
# --------------------------------------------------------------------------- #

def test_eo_ria_01__returns_account_id(db, M, O):
    """EO-RIA-01 — account_id=7 -> returns 7.
    Rules: resolve_invoice_account_id R1."""
    o = O()
    mutate(db, o, account_id=7)
    assert M.resolve_invoice_account_id(o) == 7


def test_eo_ria_02__none_account_id_rejected(db, M, O):
    """EO-RIA-02 — account_id=None -> 422.
    Rules: resolve_invoice_account_id R2."""
    o = O()
    mutate(db, o, account_id=None)
    with pytest.raises(HTTPException) as exc:
        M.resolve_invoice_account_id(o)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Set an account on the expense order before creating an invoice"


def test_eo_ria_03__zero_account_id_rejected(db, M, O):
    """EO-RIA-03 — account_id=0 -> 422.
    Rules: resolve_invoice_account_id R2."""
    o = O()
    mutate(db, o, account_id=0)
    with pytest.raises(HTTPException) as exc:
        M.resolve_invoice_account_id(o)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Set an account on the expense order before creating an invoice"


def test_eo_ria_04__boundary_account_id_one(db, M, O):
    """EO-RIA-04 — account_id=1 -> returns 1.
    Rules: resolve_invoice_account_id R1."""
    o = O()
    mutate(db, o, account_id=1)
    assert M.resolve_invoice_account_id(o) == 1


# --------------------------------------------------------------------------- #
# `reset_approvals`
# --------------------------------------------------------------------------- #

def test_eo_ra_01__clears_approved_logs_event(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-RA-01 — clears every approved row of this order, logs one event; other
    order untouched.
    Rules: reset_approvals R1, R2, R3."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False, assigned_at=T0)
    p = O()
    approver_factory(p, u1, assigned_by=u1, approved=True, approved_at=T0)

    result = M.reset_approvals(db, o.id, w1.id, u2.id)

    assert result is None
    rows = {a.user_id: a for a in approvers_of(db, o.id)}
    assert rows[u1.id].approved is False and rows[u1.id].approved_at is None
    assert rows[u2.id].approved is False and rows[u2.id].approved_at is None
    assert rows[u3.id].approved is False and rows[u3.id].assigned_at == T0
    p_rows = {a.user_id: a for a in approvers_of(db, p.id)}
    assert p_rows[u1.id].approved is True and p_rows[u1.id].approved_at == T0

    o_events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in o_events] == [
        ("approvals_reset", "Section unconfirmed (2 approval(s) cleared)")
    ]
    assert o_events[0].performed_by == u2.id
    assert o_events[0].metadata_json is None
    assert events_of(db, p.id) == []


def test_eo_ra_02__custom_reason(db, M, w1, O, u1, u2, approver_factory):
    """EO-RA-02 — a custom reason prefix is used in the event description.
    Rules: reset_approvals R3."""
    o = O()
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)

    result = M.reset_approvals(db, o.id, w1.id, u1.id, reason="Order details edited")

    assert result is None
    row = approver_row(db, o.id, u2.id)
    assert row.approved is False
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [
        ("approvals_reset", "Order details edited (1 approval(s) cleared)")
    ]
    assert events[0].performed_by == u1.id


def test_eo_ra_03__nothing_approved_is_noop(db, M, w1, O, u1, u2, approver_factory):
    """EO-RA-03 — nobody approved yet -> no change, no event.
    Rules: reset_approvals R4."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=False)
    approver_factory(o, u2, assigned_by=u1, approved=False)

    result = M.reset_approvals(db, o.id, w1.id, u1.id)

    assert result is None
    rows = approvers_of(db, o.id)
    assert all(not a.approved for a in rows)
    assert events_of(db, o.id) == []


def test_eo_ra_04__no_approvers_is_noop(db, M, w1, O, u1):
    """EO-RA-04 — no approver rows at all -> no change, no event.
    Rules: reset_approvals R4."""
    o = O()
    result = M.reset_approvals(db, o.id, w1.id, u1.id)
    assert result is None
    assert events_of(db, o.id) == []


def test_eo_ra_05__other_workspace_approver_untouched(db, M, w1, w2, O, u1, u4, approver_factory):
    """EO-RA-05 — an approver row under another workspace is not cleared and no
    event is logged.
    Rules: reset_approvals R2 (isolation)."""
    o = O()
    approver_factory(o, u4, assigned_by=u1, approved=True, approved_at=T0, workspace_id=w2.id)

    result = M.reset_approvals(db, o.id, w1.id, u1.id)

    assert result is None
    row = approver_row(db, o.id, u4.id)
    assert row.approved is True and row.approved_at == T0
    assert events_of(db, o.id) == []


# --------------------------------------------------------------------------- #
# `_format_scalar_value`
# --------------------------------------------------------------------------- #

def test_eo_fs_01__none_is_dash(M):
    """EO-FS-01 — None -> '—'.
    Rules: _format_scalar_value R1."""
    assert M._format_scalar_value("due_date", None) == "—"


def test_eo_fs_02__date_isoformat(M):
    """EO-FS-02 — a date -> ISO text.
    Rules: _format_scalar_value R2."""
    assert M._format_scalar_value("expense_date", date(2026, 3, 5)) == "2026-03-05"


def test_eo_fs_03__datetime_isoformat(M):
    """EO-FS-03 — a datetime -> ISO text.
    Rules: _format_scalar_value R2."""
    assert M._format_scalar_value("x", datetime(2026, 3, 5, 14, 30, 0)) == "2026-03-05T14:30:00"


def test_eo_fs_04__integral_decimal(M):
    """EO-FS-04 — an integral Decimal -> integer text.
    Rules: _format_scalar_value R3."""
    assert M._format_scalar_value("x", Decimal("10.00")) == "10"


def test_eo_fs_05__fractional_decimal_normalized(M):
    """EO-FS-05 — a fractional Decimal -> normalized text.
    Rules: _format_scalar_value R3."""
    assert M._format_scalar_value("x", Decimal("10.50")) == "10.5"


def test_eo_fs_06__zero_decimal(M):
    """EO-FS-06 — Decimal('0.00') -> '0'.
    Rules: _format_scalar_value R3."""
    assert M._format_scalar_value("x", Decimal("0.00")) == "0"


def test_eo_fs_07__string_trimmed(M):
    """EO-FS-07 — a string is trimmed.
    Rules: _format_scalar_value R4."""
    assert M._format_scalar_value("description", "  Rent  ") == "Rent"


def test_eo_fs_08__whitespace_string_is_dash(M):
    """EO-FS-08 — whitespace-only string -> '—'.
    Rules: _format_scalar_value R4."""
    assert M._format_scalar_value("description", "   ") == "—"


def test_eo_fs_09__empty_string_is_dash(M):
    """EO-FS-09 — empty string -> '—'.
    Rules: _format_scalar_value R4."""
    assert M._format_scalar_value("description", "") == "—"


def test_eo_fs_10__zero_int(M):
    """EO-FS-10 — int 0 -> '0'.
    Rules: _format_scalar_value R4."""
    assert M._format_scalar_value("required_approvals", 0) == "0"


def test_eo_fs_11__false_bool(M):
    """EO-FS-11 — False -> 'False'.
    Rules: _format_scalar_value R4."""
    assert M._format_scalar_value("x", False) == "False"


def test_eo_fs_12__field_name_does_not_matter(M):
    """EO-FS-12 — the field name does not change the formatting.
    Rules: _format_scalar_value R5."""
    assert M._format_scalar_value("account_id", 12) == "12"
    assert M._format_scalar_value("totally_unknown", 12) == "12"


# --------------------------------------------------------------------------- #
# `_collect_field_changes`
# --------------------------------------------------------------------------- #

def _cf_record(**over):
    fields = dict(
        account_id=1, expense_category="factory", cost_center_id=5,
        expense_date=date(2026, 3, 1), due_date=None, description="Rent",
        required_approvals=None,
    )
    fields.update(over)
    return ExpenseOrder(**fields)


def test_eo_cf_01__all_tracked_fields_in_output_order(M):
    """EO-CF-01 — every tracked field that changed, in the fixed output order,
    regardless of the update dict's key order.
    Rules: _collect_field_changes R1, R2."""
    record = _cf_record()
    update_dict = {
        "required_approvals": 2,
        "description": "Rent April",
        "due_date": date(2026, 3, 31),
        "expense_date": date(2026, 3, 2),
        "cost_center_id": 6,
        "expense_category": "department",
        "account_id": 2,
    }
    changes = M._collect_field_changes(record, update_dict)
    assert changes == [
        {"field": "account_id", "label": "Account", "from_value": "1", "to_value": "2"},
        {"field": "expense_category", "label": "Category", "from_value": "factory", "to_value": "department"},
        {"field": "cost_center_id", "label": "Cost center", "from_value": "5", "to_value": "6"},
        {"field": "expense_date", "label": "Expense date", "from_value": "2026-03-01", "to_value": "2026-03-02"},
        {"field": "due_date", "label": "Due date", "from_value": "—", "to_value": "2026-03-31"},
        {"field": "description", "label": "Description", "from_value": "Rent", "to_value": "Rent April"},
        {"field": "required_approvals", "label": "Required approvals", "from_value": "—", "to_value": "2"},
    ]


def test_eo_cf_02__same_values_no_changes(M):
    """EO-CF-02 — values equal to stored ones produce no entries.
    Rules: _collect_field_changes R2."""
    record = _cf_record()
    assert M._collect_field_changes(record, {"description": "Rent", "account_id": 1}) == []


def test_eo_cf_03__empty_update_dict(M):
    """EO-CF-03 — empty update dict -> [].
    Rules: _collect_field_changes R2."""
    record = _cf_record()
    assert M._collect_field_changes(record, {}) == []


def test_eo_cf_04__only_changed_field_listed(M):
    """EO-CF-04 — only the field that actually changed is listed.
    Rules: _collect_field_changes R2."""
    record = _cf_record()
    changes = M._collect_field_changes(record, {"description": "Rent", "due_date": date(2026, 4, 1)})
    assert changes == [
        {"field": "due_date", "label": "Due date", "from_value": "—", "to_value": "2026-04-01"}
    ]


def test_eo_cf_05__untracked_fields_never_appear(M):
    """EO-CF-05 — invoice_id / updated_by are not tracked fields.
    Rules: _collect_field_changes R3."""
    record = _cf_record(invoice_id=None)
    assert M._collect_field_changes(record, {"invoice_id": 9, "updated_by": 3}) == []


def test_eo_cf_06__whitespace_only_difference_counts(M):
    """EO-CF-06 — a trailing-space difference still counts as a change.
    Rules: _collect_field_changes R4."""
    record = _cf_record()
    changes = M._collect_field_changes(record, {"description": "Rent "})
    assert changes == [
        {"field": "description", "label": "Description", "from_value": "Rent", "to_value": "Rent"}
    ]


def test_eo_cf_07__clearing_to_none_formats_as_dash(M):
    """EO-CF-07 — clearing a value to None formats the 'to' side as '—'.
    Rules: _collect_field_changes R2."""
    record = _cf_record(due_date=date(2026, 3, 31))
    changes = M._collect_field_changes(record, {"due_date": None})
    assert changes == [
        {"field": "due_date", "label": "Due date", "from_value": "2026-03-31", "to_value": "—"}
    ]


# --------------------------------------------------------------------------- #
# `_guard_confirmed_updates`
# --------------------------------------------------------------------------- #

def test_eo_gcu_01__completed_nonempty_rejected(M):
    """EO-GCU-01 — completed order, non-empty payload -> 400.
    Rules: _guard_confirmed_updates R1."""
    record = ExpenseOrder(completed_at=T0, voided=False)
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(record, {"description": "x"})
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete and cannot be edited"


def test_eo_gcu_02__completed_empty_payload_passes(M):
    """EO-GCU-02 — completed order, empty payload -> passes.
    Rules: _guard_confirmed_updates R2."""
    record = ExpenseOrder(completed_at=T0, voided=False)
    assert M._guard_confirmed_updates(record, {}) is None


@pytest.mark.xfail(strict=True, reason=BUG_754 + " — fails today on: no exception raised")
def test_eo_gcu_03__bug_754_voided_nonempty_rejected(M):
    """EO-GCU-03 — voided order, non-empty payload -> 400.
    Rules: _guard_confirmed_updates R3 [BUG-754]."""
    record = ExpenseOrder(completed_at=None, voided=True)
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(record, {"description": "x"})
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"


def test_eo_gcu_04__voided_empty_payload_passes(M):
    """EO-GCU-04 — voided order, empty payload -> passes.
    Rules: _guard_confirmed_updates R4."""
    record = ExpenseOrder(completed_at=None, voided=True)
    assert M._guard_confirmed_updates(record, {}) is None


def test_eo_gcu_05__neither_passes(M):
    """EO-GCU-05 — neither completed nor voided -> passes.
    Rules: _guard_confirmed_updates R5."""
    record = ExpenseOrder(completed_at=None, voided=False)
    assert M._guard_confirmed_updates(record, {"description": "x"}) is None


# --------------------------------------------------------------------------- #
# `_guard_item_mutations`
# --------------------------------------------------------------------------- #

def test_eo_gim_01__completed_rejected(M):
    """EO-GIM-01 — completed order -> 400.
    Rules: _guard_item_mutations R1."""
    record = ExpenseOrder(completed_at=T0, voided=False)
    with pytest.raises(HTTPException) as exc:
        M._guard_item_mutations(record)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"


@pytest.mark.xfail(strict=True, reason=BUG_754 + " — fails today on: no exception raised")
def test_eo_gim_02__bug_754_voided_rejected(M):
    """EO-GIM-02 — voided order -> 400.
    Rules: _guard_item_mutations R2 [BUG-754]."""
    record = ExpenseOrder(completed_at=None, voided=True)
    with pytest.raises(HTTPException) as exc:
        M._guard_item_mutations(record)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"


def test_eo_gim_03__neither_passes(M):
    """EO-GIM-03 — neither completed nor voided -> passes.
    Rules: _guard_item_mutations R3."""
    record = ExpenseOrder(completed_at=None, voided=False)
    assert M._guard_item_mutations(record) is None


# --------------------------------------------------------------------------- #
# `_prepare_item_dict` and the item schemas
# --------------------------------------------------------------------------- #

def test_eo_pid_01__computes_subtotal_in_place(M):
    """EO-PID-01 — mutates and returns the same dict; other keys unchanged.
    Rules: _prepare_item_dict R1."""
    d = {"description": "Rent", "quantity": Decimal("3"), "unit_price": Decimal("33.33")}
    result = M._prepare_item_dict(d)
    assert result is d
    assert d["line_subtotal"] == Decimal("99.99")
    assert d["description"] == "Rent"


def test_eo_pid_02__exact_product_not_rounded(M):
    """EO-PID-02 — subtotal is the exact (unrounded) product.
    Rules: _prepare_item_dict R1."""
    d = {"quantity": Decimal("2.5"), "unit_price": Decimal("4.10")}
    M._prepare_item_dict(d)
    assert d["line_subtotal"] == Decimal("10.250")


def test_eo_pid_03__missing_unit_price_only(M):
    """EO-PID-03 — no quantity key -> defaults to 1.
    Rules: _prepare_item_dict R2."""
    d = {"unit_price": Decimal("12.50")}
    M._prepare_item_dict(d)
    assert d["line_subtotal"] == Decimal("12.50")


def test_eo_pid_04__none_unit_price(M):
    """EO-PID-04 — unit_price=None -> subtotal 0.
    Rules: _prepare_item_dict R3."""
    d = {"quantity": Decimal("4"), "unit_price": None}
    M._prepare_item_dict(d)
    assert d["line_subtotal"] == 0


def test_eo_pid_05__missing_unit_price_key(M):
    """EO-PID-05 — no unit_price key -> subtotal 0.
    Rules: _prepare_item_dict R3."""
    d = {"quantity": Decimal("4")}
    M._prepare_item_dict(d)
    assert d["line_subtotal"] == 0


def test_eo_pid_06__zero_unit_price(M):
    """EO-PID-06 — unit_price=0 -> subtotal 0.
    Rules: _prepare_item_dict R3."""
    d = {"quantity": Decimal("4"), "unit_price": Decimal("0")}
    M._prepare_item_dict(d)
    assert d["line_subtotal"] == 0


@pytest.mark.xfail(strict=True, reason=BUG_021 + " — fails today on: no ValidationError")
def test_eo_pid_07__bug_021_more_than_2_decimals_quantity():
    """EO-PID-07 — quantity with more than 2 decimals is rejected.
    Rules: _prepare_item_dict R1 [BUG-021]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(description="x", quantity=Decimal("1.005"), unit_price=Decimal("10"))


@pytest.mark.xfail(strict=True, reason=BUG_021 + " — fails today on: no ValidationError")
def test_eo_pid_08__bug_021_more_than_2_decimals_price():
    """EO-PID-08 — unit_price with more than 2 decimals is rejected.
    Rules: _prepare_item_dict R1 [BUG-021]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(description="x", quantity=Decimal("1"), unit_price=Decimal("33.333"))


@pytest.mark.xfail(strict=True, reason=BUG_021 + " — fails today on: no ValidationError")
def test_eo_pid_09__bug_021_too_many_integer_digits():
    """EO-PID-09 — unit_price with 14 integer digits is rejected.
    Rules: _prepare_item_dict R1 [BUG-021]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(
            description="x", quantity=1, unit_price=Decimal("10000000000000.00")
        )


def test_eo_pid_10__boundary_13_digits_2_decimals_accepted():
    """EO-PID-10 — 2 decimals / 13 integer digits is the accepted boundary.
    Rules: _prepare_item_dict R1."""
    item = ExpenseOrderItemCreate(
        description="x", quantity=Decimal("1.25"), unit_price=Decimal("9999999999999.99")
    )
    assert item.quantity == Decimal("1.25")
    assert item.unit_price == Decimal("9999999999999.99")


@pytest.mark.xfail(strict=True, reason=BUG_021 + " — fails today on: no ValidationError")
def test_eo_pid_11__bug_021_update_schema_rejects_precision():
    """EO-PID-11 — ExpenseOrderItemUpdate rejects the same precision/size violations.
    Rules: _prepare_item_dict R1 [BUG-021]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(quantity=Decimal("1.005"))
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(unit_price=Decimal("10000000000000"))


@pytest.mark.xfail(strict=True, reason=BUG_362 + " — fails today on: no ValidationError")
def test_eo_pid_12__bug_362_zero_quantity_rejected():
    """EO-PID-12 — quantity=0 is rejected.
    Rules: _prepare_item_dict R1 [BUG-362]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(description="x", quantity=0, unit_price=10)


@pytest.mark.xfail(strict=True, reason=BUG_362 + " — fails today on: no ValidationError")
def test_eo_pid_13__bug_362_negative_quantity_rejected():
    """EO-PID-13 — negative quantity is rejected.
    Rules: _prepare_item_dict R1 [BUG-362]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(description="x", quantity=-5, unit_price=10)


@pytest.mark.xfail(strict=True, reason=BUG_362 + " — fails today on: no ValidationError")
def test_eo_pid_14__bug_362_negative_price_rejected():
    """EO-PID-14 — negative unit_price is rejected.
    Rules: _prepare_item_dict R1 [BUG-362]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemCreate(description="x", quantity=1, unit_price=Decimal("-0.01"))


def test_eo_pid_15__boundary_small_qty_zero_price_accepted():
    """EO-PID-15 — quantity=0.01, unit_price=0 builds.
    Rules: _prepare_item_dict R1."""
    item = ExpenseOrderItemCreate(description="x", quantity=Decimal("0.01"), unit_price=0)
    assert item.quantity == Decimal("0.01")


@pytest.mark.xfail(strict=True, reason=BUG_362 + " — fails today on: no ValidationError")
def test_eo_pid_16__bug_362_update_schema_rejects_range():
    """EO-PID-16 — ExpenseOrderItemUpdate rejects qty<=0 / negative price.
    Rules: _prepare_item_dict R1 [BUG-362]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(quantity=0)
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(quantity=-1)
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(unit_price=Decimal("-100"))


def test_eo_pid_17__boundary_update_small_qty_zero_price_accepted():
    """EO-PID-17 — ExpenseOrderItemUpdate(quantity=0.01, unit_price=0) builds.
    Rules: _prepare_item_dict R1."""
    item = ExpenseOrderItemUpdate(quantity=Decimal("0.01"), unit_price=0)
    assert item.quantity == Decimal("0.01")


# --------------------------------------------------------------------------- #
# `create_expense_order`
# --------------------------------------------------------------------------- #

def ws_order_count(db, ws_id):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(ExpenseOrder).where(ExpenseOrder.workspace_id == ws_id))


def test_eo_c_01__full_happy_path(db, M, w1, u1, f1, a1):
    """EO-C-01 — a full create with two items: order, lines, approver, event.
    Rules: create_expense_order R3, R5, R7, R8, R9, R10."""
    data = ExpenseOrderCreate(
        expense_category="factory", cost_center_id=f1.id, account_id=a1.id,
        expense_date=date(2026, 3, 1), due_date=date(2026, 3, 31), description="March rent",
        items=[
            ExpenseOrderItemCreate(description="Rent", quantity=1, unit_price=Decimal("5000.00")),
            ExpenseOrderItemCreate(description="Service charge", quantity=2, unit="month", unit_price=Decimal("250.50"), notes="Q1"),
        ],
    )
    eo = M.create_expense_order(db, data, w1.id, u1.id)
    assert eo.id is not None

    o = reread_order(db, eo.id)
    assert o.workspace_id == w1.id
    assert o.created_by == u1.id
    assert o.expense_category == "factory"
    assert o.cost_center_id == f1.id
    assert o.account_id == a1.id
    assert o.expense_date == date(2026, 3, 1)
    assert o.due_date == date(2026, 3, 31)
    assert o.description == "March rent"
    assert o.required_approvals is None
    assert o.invoice_id is None
    assert o.voided is False
    assert o.completed_at is None
    assert o.subtotal == Decimal("5501.00")
    assert o.total_amount == Decimal("5501.00")

    lines = {ln.line_number: ln for ln in lines_of(db, eo.id)}
    assert lines[1].description == "Rent" and lines[1].quantity == 1 and lines[1].unit_price == Decimal("5000.00") and lines[1].line_subtotal == Decimal("5000.00")
    assert lines[2].description == "Service charge" and lines[2].quantity == 2 and lines[2].unit == "month" and lines[2].unit_price == Decimal("250.50") and lines[2].notes == "Q1" and lines[2].line_subtotal == Decimal("501.00")
    for ln in lines.values():
        assert ln.workspace_id == w1.id
        assert ln.expense_order_id == eo.id

    approvers = approvers_of(db, eo.id)
    assert len(approvers) == 1
    assert approvers[0].user_id == u1.id
    assert approvers[0].assigned_by == u1.id
    assert approvers[0].approved is False
    assert approvers[0].approved_at is None

    events = events_of(db, eo.id)
    assert [(e.event_type, e.description) for e in events] == [("created", "Expense order created")]
    assert events[0].performed_by == u1.id
    assert events[0].metadata_json is None


def test_eo_c_02__first_number_of_the_year(db, M, w1, u1, f1):
    """EO-C-02 — first order of the year -> 001.
    Rules: create_expense_order R6."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    year = datetime.now().year
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-001"


def test_eo_c_03__third_number(db, M, w1, u1, f1, order_factory):
    """EO-C-03 — two existing current-year orders -> 003.
    Rules: create_expense_order R6."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year}-001")
    order_factory(w1, u1, expense_number=f"EXP-{year}-002")
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-003"


def test_eo_c_04__other_years_ignored(db, M, w1, u1, f1, order_factory):
    """EO-C-04 — a previous year's order does not affect this year's numbering.
    Rules: create_expense_order R6."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year - 1}-007")
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-001"


def test_eo_c_05__workspace_isolated_numbering(db, M, w1, w2, u1, u4, f1, order_factory):
    """EO-C-05 — another workspace's numbers do not affect this workspace.
    Rules: create_expense_order R6 (isolation)."""
    year = datetime.now().year
    order_factory(w2, u4, expense_number=f"EXP-{year}-005")
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-001"


def test_eo_c_06__rolls_to_four_digits(db, M, w1, u1, f1, order_factory):
    """EO-C-06 — EXP-<year>-999 -> next is 1000.
    Rules: create_expense_order R6."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year}-999")
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-1000"


@pytest.mark.xfail(strict=True, reason=BUG_749 + " — fails today on: IntegrityError (retries …-1000)")
def test_eo_c_07__bug_749_numeric_max_not_text_max(db, M, w1, u1, f1, order_factory):
    """EO-C-07 — numbering must use the numeric max of the year's suffixes, not
    a text comparison (999 and 1000 both present -> next is 1001).
    Rules: create_expense_order R6 [BUG-749]."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year}-999")
    order_factory(w1, u1, expense_number=f"EXP-{year}-1000")
    with db.begin_nested():
        eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-1001"


@pytest.mark.xfail(strict=True, reason=BUG_749 + " — fails today on: IntegrityError from the workspace-wide unique index")
def test_eo_c_08__bug_749_numbers_unique_per_workspace_only(db, M, w1, w2, u1, u4, order_factory):
    """EO-C-08 — a second workspace's first order of the year must not collide
    with another workspace's existing number.
    Rules: create_expense_order R6 [BUG-749]."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year}-001")
    with db.begin_nested():
        eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="other", description="B"), w2.id, u4.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-001"
    assert ws_order_count(db, w1.id) == 1


def test_eo_c_09__numeric_max_with_gap(db, M, w1, u1, f1, order_factory):
    """EO-C-09 — numeric max of the existing suffixes (10, not 2) + 1.
    Rules: create_expense_order R6."""
    year = datetime.now().year
    order_factory(w1, u1, expense_number=f"EXP-{year}-002")
    order_factory(w1, u1, expense_number=f"EXP-{year}-010")
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_number == f"EXP-{year}-011"


def test_eo_c_10__invalid_category(db, M, w1, u1, f1):
    """EO-C-10 — wrong-case category -> 400, nothing written.
    'Nothing written' checked via the full ws_counts() tuple (orders, lines,
    approvers, events), not just the order count (verifier finding #6).
    Rules: create_expense_order R1 / Errors R1."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="Factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg("Factory")
    assert ws_counts(db, w1.id) == before


def test_eo_c_11__factory_missing_cost_center(db, M, w1, u1):
    """EO-C-11 — factory with no cost center -> 400, nothing written.
    Rules: create_expense_order R1 / Errors R1."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=None, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this expense order"
    assert ws_counts(db, w1.id) == before


def test_eo_c_12__factory_other_workspace(db, M, w1, u1, f2):
    """EO-C-12 — a factory of another workspace -> 404, nothing written.
    Rules: create_expense_order R1 / Errors R1."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f2.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"
    assert ws_counts(db, w1.id) == before


@pytest.mark.xfail(strict=True, reason=BUG_340 + " — fails today on: order created")
def test_eo_c_13__bug_340_soft_deleted_factory_rejected(db, M, w1, u1, fd):
    """EO-C-13 — a soft-deleted factory of this workspace -> 404, nothing written.
    Rules: create_expense_order R1 [BUG-340]."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=fd.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"
    assert ws_counts(db, w1.id) == before


def test_eo_c_14__category_checked_before_description(db, M, w1, u1):
    """EO-C-14 — an invalid category wins over the blank-description check.
    Rules: create_expense_order R1, R2."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="bogus", description="   "), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg("bogus")
    assert ws_counts(db, w1.id) == before


def test_eo_c_15__none_description_rejected(db, M, w1, u1, f1):
    """EO-C-15 — description=None -> 400, nothing written.
    Rules: create_expense_order R2 / Errors R2."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description=None), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert ws_counts(db, w1.id) == before


def test_eo_c_16__empty_description_rejected(db, M, w1, u1, f1):
    """EO-C-16 — description='' -> 400, nothing written.
    Rules: create_expense_order R2 / Errors R2."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description=""), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert ws_counts(db, w1.id) == before


def test_eo_c_17__whitespace_description_rejected(db, M, w1, u1, f1):
    """EO-C-17 — description='   ' -> 400, nothing written.
    Rules: create_expense_order R2 / Errors R2."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="   "), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert ws_counts(db, w1.id) == before


def test_eo_c_18__description_not_trimmed(db, M, w1, u1, f1):
    """EO-C-18 — a description with surrounding spaces is stored as given.
    Rules: create_expense_order R2, R3."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description=" a "), w1.id, u1.id)
    assert reread_order(db, eo.id).description == " a "


def test_eo_c_19__other_category_no_cost_center(db, M, w1, u1):
    """EO-C-19 — category other, no cost center -> created.
    Rules: create_expense_order R3."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="other", cost_center_id=None, description="Tea"), w1.id, u1.id)
    o = reread_order(db, eo.id)
    assert o.expense_category == "other"
    assert o.cost_center_id is None


def test_eo_c_20__other_with_cost_center_sent_no_error(db, M, w1, u1, f1):
    """EO-C-20 — category other with a cost center sent is accepted (no lookup).
    Rules: create_expense_order R3, _validate_order_allocation R2."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="other", cost_center_id=f1.id, description="Tea"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_category == "other"


@pytest.mark.xfail(strict=True, reason=BUG_752 + " — fails today on: cost_center_id == F1.id")
def test_eo_c_21__bug_752_other_category_clears_cost_center(db, M, w1, u1, f1):
    """EO-C-21 — category other must store cost_center_id as null.
    Rules: create_expense_order R3 [BUG-752]."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="other", cost_center_id=f1.id, description="Tea"), w1.id, u1.id)
    assert reread_order(db, eo.id).cost_center_id is None


def test_eo_c_22__default_expense_date_is_today(db, M, w1, u1, f1):
    """EO-C-22 — no expense_date given -> today's date.
    Rules: create_expense_order R4."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A"), w1.id, u1.id)
    assert reread_order(db, eo.id).expense_date == date.today()


def test_eo_c_23__items_none(db, M, w1, u1, f1):
    """EO-C-23 — items=None -> zero totals, 0 lines, 1 approver, 1 event.
    Rules: create_expense_order R9."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A", items=None), w1.id, u1.id)
    o = reread_order(db, eo.id)
    assert o.subtotal == 0 and o.total_amount == 0
    assert lines_of(db, eo.id) == []
    assert len(approvers_of(db, eo.id)) == 1
    assert len(events_of(db, eo.id)) == 1


def test_eo_c_24__items_empty_list(db, M, w1, u1, f1):
    """EO-C-24 — items=[] -> zero totals, 0 lines.
    Rules: create_expense_order R9."""
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A", items=[]), w1.id, u1.id)
    o = reread_order(db, eo.id)
    assert o.subtotal == 0 and o.total_amount == 0
    assert lines_of(db, eo.id) == []


def test_eo_c_25__lines_in_given_order(db, M, w1, u1, f1):
    """EO-C-25 — lines are numbered in the given order, not alphabetical.
    Rules: create_expense_order R8."""
    eo = M.create_expense_order(
        db,
        ExpenseOrderCreate(
            expense_category="factory", cost_center_id=f1.id, description="A",
            items=[
                ExpenseOrderItemCreate(description="Zeta", quantity=1, unit_price=1),
                ExpenseOrderItemCreate(description="Alpha", quantity=1, unit_price=2),
                ExpenseOrderItemCreate(description="Mid", quantity=1, unit_price=3),
            ],
        ),
        w1.id, u1.id,
    )
    lines = {ln.line_number: ln.description for ln in lines_of(db, eo.id)}
    assert lines == {1: "Zeta", 2: "Alpha", 3: "Mid"}
    assert reread_order(db, eo.id).total_amount == Decimal("6.00")


def test_eo_c_26__missing_quantity_defaults_to_1(db, M, w1, u1, f1):
    """EO-C-26 — a line with no quantity given defaults to 1.
    Rules: create_expense_order R8, _prepare_item_dict R2."""
    item = ExpenseOrderItemCreate(description="Fee", unit_price=40)
    eo = M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, description="A", items=[item]), w1.id, u1.id)
    lines = lines_of(db, eo.id)
    assert lines[0].quantity == 1
    assert lines[0].line_subtotal == Decimal("40.00")
    assert reread_order(db, eo.id).total_amount == Decimal("40.00")


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: order created with W2's account")
def test_eo_c_27__bug_750_other_workspace_account_rejected(db, M, w1, u1, f1, aw2):
    """EO-C-27 — an account of another workspace -> 404, nothing written.
    Setup fixed per cases revision 4: cost_center_id=F1.id (the section's
    default create payload), so the call reaches the account check instead of
    failing earlier on the factory-required check.
    Rules: create_expense_order R12 [BUG-750]."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, account_id=aw2.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert ws_counts(db, w1.id) == before


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: order created")
def test_eo_c_28__bug_750_soft_deleted_account_rejected(db, M, w1, u1, f1, ax):
    """EO-C-28 — a soft-deleted account -> 404, nothing written.
    Rules: create_expense_order R12 [BUG-750]."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, account_id=ax.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert ws_counts(db, w1.id) == before


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: IntegrityError raised instead of HTTPException")
def test_eo_c_29__bug_750_missing_account_rejected(db, M, w1, u1, f1):
    """EO-C-29 — a non-existent account id -> HTTPException 404, not IntegrityError.
    Rules: create_expense_order R12 [BUG-750]."""
    before = ws_counts(db, w1.id)
    missing = missing_id(db, Account)
    with db.begin_nested(), pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="factory", cost_center_id=f1.id, account_id=missing, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert ws_counts(db, w1.id) == before


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: field present")
def test_eo_c_30__bug_750_order_template_id_removed_from_schema():
    """EO-C-30 — order_template_id must not be a client-settable create field.
    Rules: create_expense_order Inputs [BUG-750]."""
    assert "order_template_id" not in ExpenseOrderCreate.model_fields


def test_eo_c_31__department_other_workspace(db, M, w1, u1, d2):
    """EO-C-31 — a department of another workspace -> 404, nothing written.
    Rules: create_expense_order R1 (isolation)."""
    before = ws_counts(db, w1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_expense_order(db, ExpenseOrderCreate(expense_category="department", cost_center_id=d2.id, description="A"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"
    assert ws_counts(db, w1.id) == before


# --------------------------------------------------------------------------- #
# `update_expense_order`
# --------------------------------------------------------------------------- #
# Default Given: O = default order with account A1, factory F1, due_date
# 2026-03-31, description "Rent March". call(d) = update_expense_order(db,
# o.id, ExpenseOrderUpdate(**d), w1.id, u2.id).

def business_fields_unchanged(before, after):
    """Compare two order_snap() dicts ignoring updated_by -- that column's own
    behavior (BUG-740) is asserted by its own dedicated cases (U-26/27/28)."""
    b, a = dict(before), dict(after)
    b.pop("updated_by", None)
    a.pop("updated_by", None)
    assert a == b


def lines_approvers_snap(db, order_id):
    """Snapshot of an order's lines and approvers (for 'unchanged' assertions)."""
    return (
        [(l.id, l.line_number, l.description, l.quantity, l.unit_price, l.line_subtotal) for l in lines_of(db, order_id)],
        [(a.id, a.user_id, a.approved, a.approved_at, a.assigned_by) for a in approvers_of(db, order_id)],
    )


def uo(O, f1, a1, **over):
    fields = dict(account_id=a1.id, cost_center_id=f1.id, due_date=date(2026, 3, 31), description="Rent March")
    fields.update(over)
    return O(**fields)


def call_u(db, M, o, w1, u2, **d):
    return M.update_expense_order(db, o.id, ExpenseOrderUpdate(**d), w1.id, u2.id)


def test_eo_u_01__description_change_logged(db, M, w1, O, f1, a1, u2):
    """EO-U-01 — a description change logs one 'updated' event with the change.
    Rules: update_expense_order R2, R7, R10."""
    o = uo(O, f1, a1)
    before_date, before_due = o.expense_date, o.due_date
    result = call_u(db, M, o, w1, u2, description="Rent April")
    assert result.id == o.id
    assert result._approvals_reset is False
    r = reread_order(db, o.id)
    assert r.description == "Rent April"
    assert r.account_id == a1.id and r.expense_category == "factory" and r.cost_center_id == f1.id
    assert r.expense_date == before_date and r.due_date == before_due
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [("updated", "Order details updated")]
    assert events[0].performed_by == u2.id
    assert events[0].metadata_json == {
        "changes": [{"field": "description", "label": "Description", "from_value": "Rent March", "to_value": "Rent April"}]
    }


def test_eo_u_02__updated_by_stamped(db, M, w1, O, f1, a1, u2):
    """EO-U-02 — updated_by is stamped with the acting user.
    Rules: update_expense_order R14."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, description="Rent April")
    assert reread_order(db, o.id).updated_by == u2.id


def test_eo_u_03__missing_order_404(db, M, w1, O, f1, a1, u2):
    """EO-U-03 — a non-existent order id -> 404, nothing written.
    Rules: update_expense_order R1 / Errors R1."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, type("X", (), {"id": missing}), w1, u2, description="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)
    assert order_snap(db, o.id) == snap_before
    assert events_of(db, o.id) == []


def test_eo_u_04__other_workspace_order_404(db, M, w1, O5, u2):
    """EO-U-04 — the id belongs to another workspace's order -> 404, nothing written.
    Rules: update_expense_order R1 (isolation)."""
    snap_before = order_snap(db, O5.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, O5, w1, u2, description="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert order_snap(db, O5.id) == snap_before


def test_eo_u_05__completed_nonempty_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-05 — completed order, non-empty payload -> 400, nothing written.
    'Nothing written' per Conventions covers lines/approvers/events too (O has
    none to begin with, so they must stay empty) -- verifier finding #6.
    Rules: update_expense_order R3 / Errors R3."""
    o = uo(O, f1, a1, completed_at=T0)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, description="x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete and cannot be edited"
    assert order_snap(db, o.id) == snap_before
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []


def test_eo_u_06__completed_empty_payload_passes(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-06 — completed order, empty payload -> passes, nothing changes.
    'All fields unchanged' is read as the business fields, not the
    BUG-740 updated_by side effect, which U-26/U-27/U-28 cover on their own
    (best-practice default, delegated by reviewer).
    Rules: update_expense_order R3 (boundary)."""
    o = uo(O, f1, a1, completed_at=T0)
    approver_factory(o, u3, assigned_by=u2, approved=False)
    snap_before = order_snap(db, o.id)
    la_before = lines_approvers_snap(db, o.id)
    result = call_u(db, M, o, w1, u2)
    assert result.id == o.id
    assert result._approvals_reset is False
    business_fields_unchanged(snap_before, order_snap(db, o.id))
    assert lines_approvers_snap(db, o.id) == la_before
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_754 + " — fails today on: no exception, description changed")
def test_eo_u_07__bug_754_voided_nonempty_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-07 — voided order, non-empty payload -> 400, nothing written.
    Rules: update_expense_order R3 [BUG-754]."""
    o = uo(O, f1, a1, voided=True)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, description="x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert order_snap(db, o.id) == snap_before


def test_eo_u_08__voided_empty_payload_passes(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-08 — voided order, empty payload -> passes.
    'Fields unchanged' excludes the BUG-740 updated_by side effect, covered
    separately by U-26/U-27/U-28 (best-practice default, delegated by reviewer).
    Rules: update_expense_order R3, _guard_confirmed_updates R4."""
    o = uo(O, f1, a1, voided=True)
    approver_factory(o, u3, assigned_by=u2, approved=False)
    snap_before = order_snap(db, o.id)
    la_before = lines_approvers_snap(db, o.id)
    result = call_u(db, M, o, w1, u2)
    assert result.id == o.id
    assert result._approvals_reset is False
    business_fields_unchanged(snap_before, order_snap(db, o.id))
    assert lines_approvers_snap(db, o.id) == la_before
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_741 + " — fails today on: no captured FOR UPDATE")
def test_eo_u_09__bug_741_locks_order_row(db, M, w1, O, f1, a1, u2, engine):
    """EO-U-09 — the order row is read FOR UPDATE before the state checks.
    Rules: update_expense_order R3, R13 [BUG-741]."""
    o = uo(O, f1, a1)
    with SQLCapture(engine) as cap:
        result = call_u(db, M, o, w1, u2, description="Rent April")
    assert result.id == o.id
    assert cap.locked


def test_eo_u_10__invalid_category_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-10 — an invalid expense_category -> 400, nothing written.
    Rules: update_expense_order R4 / Errors R4."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, expense_category="Factory")
    assert exc.value.status_code == 400
    assert exc.value.detail == invalid_category_msg("Factory")
    assert order_snap(db, o.id) == snap_before
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []


def test_eo_u_11__cost_center_other_workspace_factory_rejected(db, M, w1, O, f1, a1, u2, f2):
    """EO-U-11 — a factory of another workspace -> 404, nothing written.
    Rules: update_expense_order R4 / Errors R4."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, cost_center_id=f2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"
    assert order_snap(db, o.id) == snap_before
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []


def test_eo_u_12__category_and_cost_center_changed_together(db, M, w1, O, f1, a1, u2, d1):
    """EO-U-12 — both category and cost center change; events list both changes
    in field order.
    Rules: update_expense_order R4 (happy)."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, expense_category="department", cost_center_id=d1.id)
    r = reread_order(db, o.id)
    assert r.expense_category == "department" and r.cost_center_id == d1.id
    events = events_of(db, o.id)
    assert events[0].metadata_json["changes"] == [
        {"field": "expense_category", "label": "Category", "from_value": "factory", "to_value": "department"},
        {"field": "cost_center_id", "label": "Cost center", "from_value": str(f1.id), "to_value": str(d1.id)},
    ]


def test_eo_u_13__category_change_merges_stored_cost_center(db, M, w1, O, f1, a1, u2, d1):
    """EO-U-13 — category changed alone merges in the stored cost center id,
    which is not a valid department id -> 404, nothing written.
    Rules: update_expense_order R4 (boundary)."""
    assert d1.id != f1.id
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, expense_category="department")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"
    assert order_snap(db, o.id) == snap_before
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []


def test_eo_u_14__cost_center_changed_alone(db, M, w1, O, f1, a1, u2, f3):
    """EO-U-14 — cost center changed alone keeps the stored category.
    Rules: update_expense_order R4 (boundary)."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, cost_center_id=f3.id)
    r = reread_order(db, o.id)
    assert r.cost_center_id == f3.id and r.expense_category == "factory"


def test_eo_u_15__allocation_not_rechecked_when_absent(db, M, w1, O, f1, a1, u2):
    """EO-U-15 — neither category nor cost center in the payload -> allocation
    is not re-checked, even if the stored factory was since soft-deleted.
    Rules: update_expense_order R5."""
    o = uo(O, f1, a1)
    mutate(db, f1, is_deleted=True)
    db.flush()
    call_u(db, M, o, w1, u2, description="Rent April")
    r = reread_order(db, o.id)
    assert r.description == "Rent April"
    assert r.cost_center_id == f1.id


def test_eo_u_16__change_to_other_no_exception(db, M, w1, O, f1, a1, u2):
    """EO-U-16 — changing category to 'other' succeeds with no exception.
    Rules: update_expense_order R4, R6."""
    o = uo(O, f1, a1)
    result = call_u(db, M, o, w1, u2, expense_category="other")
    assert result.id == o.id
    assert reread_order(db, o.id).expense_category == "other"


@pytest.mark.xfail(strict=True, reason=BUG_752 + " — fails today on: cost_center_id == F1.id")
def test_eo_u_17__bug_752_change_to_other_clears_cost_center(db, M, w1, O, f1, a1, u2):
    """EO-U-17 — changing category to 'other' must clear the stale cost center.
    Rules: update_expense_order R6 [BUG-752]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, expense_category="other")
    assert reread_order(db, o.id).cost_center_id is None


@pytest.mark.xfail(strict=True, reason=BUG_752 + " — fails today on: cost_center_id == D1.id")
def test_eo_u_18__bug_752_other_with_cost_center_sent_still_cleared(db, M, w1, O, f1, a1, u2, d1):
    """EO-U-18 — sending a cost center alongside category 'other' is still cleared.
    Rules: update_expense_order R6 [BUG-752]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, expense_category="other", cost_center_id=d1.id)
    r = reread_order(db, o.id)
    assert r.expense_category == "other"
    assert r.cost_center_id is None


def test_eo_u_19__account_and_due_date_change_order(db, M, w1, O, f1, a1, u2, a2):
    """EO-U-19 — two changed fields are listed in the fixed field order.
    Rules: update_expense_order R7 (side-effect)."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, due_date=date(2026, 4, 15), account_id=a2.id)
    events = events_of(db, o.id)
    assert len(events) == 1
    assert events[0].metadata_json["changes"] == [
        {"field": "account_id", "label": "Account", "from_value": str(a1.id), "to_value": str(a2.id)},
        {"field": "due_date", "label": "Due date", "from_value": "2026-03-31", "to_value": "2026-04-15"},
    ]


def test_eo_u_20__same_values_no_event(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-20 — sending the same values as stored logs nothing and changes
    nothing. Cases revision 4: the Given uses U3 *pending* (no recorded
    approval) rather than approved -- an approved approver there would hit
    BUG-740's reset-on-no-op behavior, which is covered on its own by xfail
    U-22 using this same two-field payload (best-practice default, delegated
    by reviewer).
    Rules: update_expense_order R8, R10 (boundary)."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=False)
    snap_before = order_snap(db, o.id)
    result = call_u(db, M, o, w1, u2, description="Rent March", due_date=date(2026, 3, 31))
    assert result.id == o.id
    assert result._approvals_reset is False
    business_fields_unchanged(snap_before, order_snap(db, o.id))
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    assert events_of(db, o.id) == []


def test_eo_u_21__details_change_resets_approvals(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-21 — a details change resets recorded approvals; reset event logged
    before the updated event.
    Rules: update_expense_order R9, R11."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u2, approved=False)
    result = call_u(db, M, o, w1, u2, description="Rent April")
    assert result._approvals_reset is True
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    u2_row = approver_row(db, o.id, u2.id)
    assert u2_row.approved is False
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [
        ("approvals_reset", "Order details edited (1 approval(s) cleared)"),
        ("updated", "Order details updated"),
    ]
    assert events[0].performed_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_740 + " — fails today on: U3 approval cleared")
def test_eo_u_22__bug_740_unchanged_value_does_not_reset(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-22 — sending the field's current (unchanged) values must not reset
    approvals or log anything. Cases revision 4: uses U-20's two-field payload
    (description + due_date), now with U3 *approved* -- the pair that triggers
    BUG-740 (best-practice default, delegated by reviewer).
    Rules: update_expense_order R9, R10 [BUG-740]."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=True, approved_at=T0)
    result = call_u(db, M, o, w1, u2, description="Rent March", due_date=date(2026, 3, 31))
    assert result._approvals_reset is False
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is True and u3_row.approved_at == T0
    assert events_of(db, o.id) == []


def test_eo_u_23__required_approvals_only_logs_but_no_reset(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-23 — changing only required_approvals logs an 'updated' event but
    never resets approvals.
    Rules: update_expense_order R8, R10."""
    o = uo(O, f1, a1, required_approvals=None)
    approver_factory(o, u3, assigned_by=u2, approved=True, approved_at=T0)
    result = call_u(db, M, o, w1, u2, required_approvals=2)
    assert result._approvals_reset is False
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is True and u3_row.approved_at == T0
    assert reread_order(db, o.id).required_approvals == 2
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [("updated", "Order details updated")]
    assert events[0].performed_by == u2.id
    assert events[0].metadata_json == {
        "changes": [{"field": "required_approvals", "label": "Required approvals", "from_value": "—", "to_value": "2"}]
    }


def test_eo_u_24__no_recorded_approvals_no_reset(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-24 — nobody has approved yet -> no reset event, but the update event
    still logs.
    Rules: update_expense_order R10."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=False)
    result = call_u(db, M, o, w1, u2, description="Rent April")
    assert result._approvals_reset is False
    events = events_of(db, o.id)
    assert [e.event_type for e in events] == ["updated"]


def test_eo_u_25__expense_date_change_resets_approvals(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-25 — changing expense_date also resets recorded approvals.
    Rules: update_expense_order R9 (side-effect)."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=True, approved_at=T0)
    result = call_u(db, M, o, w1, u2, expense_date=date(2026, 3, 2))
    assert result._approvals_reset is True
    assert approver_row(db, o.id, u3.id).approved is False


@pytest.mark.xfail(strict=True, reason=BUG_740 + " — fails today on: updated_by == U2")
def test_eo_u_26__bug_740_empty_payload_no_updated_by(db, M, w1, O, f1, a1, u2):
    """EO-U-26 — an empty payload must not stamp updated_by.
    Rules: update_expense_order R14 [BUG-740]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2)
    assert reread_order(db, o.id).updated_by is None


@pytest.mark.xfail(strict=True, reason=BUG_740 + " — fails today on: updated_by == U2")
def test_eo_u_27__bug_740_unchanged_value_no_updated_by(db, M, w1, O, f1, a1, u2):
    """EO-U-27 — sending the stored value must not stamp updated_by.
    Rules: update_expense_order R14 [BUG-740]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, description="Rent March")
    assert reread_order(db, o.id).updated_by is None


@pytest.mark.xfail(strict=True, reason=BUG_740 + " — fails today on: updated_by == U2")
def test_eo_u_28__bug_740_completed_empty_payload_no_updated_by(db, M, w1, O, f1, a1, u2):
    """EO-U-28 — a completed order with an empty payload must not stamp updated_by.
    Rules: update_expense_order R14 [BUG-740]."""
    o = uo(O, f1, a1, completed_at=T0)
    call_u(db, M, o, w1, u2)
    assert reread_order(db, o.id).updated_by is None


def test_eo_u_29__empty_payload_boundary(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-29 — empty payload -> no change, no event.
    'Every field unchanged' excludes the BUG-740 updated_by side effect,
    covered separately by U-26/U-27/U-28 (best-practice default, delegated by
    reviewer).
    Rules: update_expense_order R2 (boundary)."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=False)
    snap_before = order_snap(db, o.id)
    la_before = lines_approvers_snap(db, o.id)
    result = call_u(db, M, o, w1, u2)
    assert result.id == o.id
    assert result._approvals_reset is False
    business_fields_unchanged(snap_before, order_snap(db, o.id))
    assert lines_approvers_snap(db, o.id) == la_before
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: due_date still 2026-03-31")
def test_eo_u_30__bug_753_explicit_null_clears_due_date(db, M, w1, O, f1, a1, u2):
    """EO-U-30 — an explicit null must clear due_date.
    Rules: update_expense_order R2 [BUG-753]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, due_date=None)
    assert reread_order(db, o.id).due_date is None
    events = events_of(db, o.id)
    assert events[0].metadata_json["changes"] == [
        {"field": "due_date", "label": "Due date", "from_value": "2026-03-31", "to_value": "—"}
    ]


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: account_id == A1.id")
def test_eo_u_31__bug_753_explicit_null_clears_account(db, M, w1, O, f1, a1, u2):
    """EO-U-31 — an explicit null must clear account_id.
    Rules: update_expense_order R2 [BUG-753]."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, account_id=None)
    assert reread_order(db, o.id).account_id is None


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no exception")
def test_eo_u_32__bug_753_explicit_null_cost_center_reaches_allocation(db, M, w1, O, f1, a1, u2):
    """EO-U-32 — an explicit null cost_center_id must reach the allocation check.
    Rules: update_expense_order R2, R4 [BUG-753]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, cost_center_id=None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this expense order"
    assert order_snap(db, o.id) == snap_before


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no ValidationError")
def test_eo_u_33__bug_753_none_category_rejected_by_schema():
    """EO-U-33 — expense_category=None must be rejected at the schema.
    Rules: update_expense_order R2 [BUG-753]."""
    with pytest.raises(ValidationError):
        ExpenseOrderUpdate(expense_category=None)


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no ValidationError")
def test_eo_u_34__bug_753_none_expense_date_rejected_by_schema():
    """EO-U-34 — expense_date=None must be rejected at the schema.
    Rules: update_expense_order R2 [BUG-753]."""
    with pytest.raises(ValidationError):
        ExpenseOrderUpdate(expense_date=None)


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: account changed to AW2")
def test_eo_u_35__bug_750_other_workspace_account_rejected(db, M, w1, O, f1, a1, u2, aw2):
    """EO-U-35 — an account of another workspace -> 404, nothing written.
    Rules: update_expense_order R12 [BUG-750]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, account_id=aw2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert order_snap(db, o.id) == snap_before


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: account changed to AX")
def test_eo_u_36__bug_750_soft_deleted_account_rejected(db, M, w1, O, f1, a1, u2, ax):
    """EO-U-36 — a soft-deleted account -> 404, nothing written.
    Rules: update_expense_order R12 [BUG-750]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, account_id=ax.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert order_snap(db, o.id) == snap_before


@pytest.mark.xfail(strict=True, reason=BUG_750 + " — fails today on: IntegrityError")
def test_eo_u_37__bug_750_missing_account_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-37 — a non-existent account id -> HTTPException 404, not IntegrityError.
    Rules: update_expense_order R12 [BUG-750]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    missing = missing_id(db, Account)
    with db.begin_nested(), pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, account_id=missing)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected account not found"
    assert order_snap(db, o.id) == snap_before


def test_eo_u_38__account_change_happy(db, M, w1, O, f1, a1, u2, a2):
    """EO-U-38 — changing to another live account of this workspace succeeds.
    Rules: update_expense_order R12 (happy)."""
    o = uo(O, f1, a1)
    call_u(db, M, o, w1, u2, account_id=a2.id)
    assert reread_order(db, o.id).account_id == a2.id


@pytest.mark.xfail(strict=True, reason=BUG_004 + " — fails today on: description stored as '   '")
def test_eo_u_39__bug_004_whitespace_description_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-39 — a whitespace-only description -> 400, nothing written.
    Rules: update_expense_order R12 [BUG-004]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, description="   ")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert order_snap(db, o.id) == snap_before


@pytest.mark.xfail(strict=True, reason=BUG_004 + " — fails today on: description stored as ''")
def test_eo_u_40__bug_004_empty_description_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-40 — an empty description -> 400, nothing written.
    Rules: update_expense_order R12 [BUG-004]."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, description="")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert order_snap(db, o.id) == snap_before


@pytest.mark.xfail(strict=True, reason=BUG_362 + " — fails today on: no ValidationError")
def test_eo_u_41__bug_362_negative_required_approvals_rejected():
    """EO-U-41 — required_approvals=-1 must be rejected at the schema.
    Rules: update_expense_order R12 [BUG-362]."""
    with pytest.raises(ValidationError):
        ExpenseOrderUpdate(required_approvals=-1)


def test_eo_u_42__required_approvals_zero_accepted():
    """EO-U-42 — required_approvals=0 builds.
    Rules: update_expense_order R12 (boundary)."""
    data = ExpenseOrderUpdate(required_approvals=0)
    assert data.required_approvals == 0


@pytest.mark.xfail(strict=True, reason=BUG_751 + " — fails today on: field present")
def test_eo_u_43__bug_751_invoice_id_removed_from_schema():
    """EO-U-43 — invoice_id must not be a client-settable update field.
    Rules: update_expense_order Inputs [BUG-751]."""
    assert "invoice_id" not in ExpenseOrderUpdate.model_fields


def test_eo_u_44__department_change_rejected_nothing_written(db, M, w1, O, f1, a1, u2):
    """EO-U-44 — changing to department with the stored (factory) cost center
    merged in -> 404; the accompanying description change is not written either.
    'Nothing written' checked on the full order snapshot (not description
    alone) plus lines/approvers/events (verifier finding #6).
    Rules: update_expense_order R4 / Errors R4."""
    o = uo(O, f1, a1)
    snap_before = order_snap(db, o.id)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, expense_category="department", description="New")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected department not found"
    assert reread_order(db, o.id).description == "Rent March"
    assert order_snap(db, o.id) == snap_before
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no exception (returns O, description unchanged)")
def test_eo_u_45__bug_753_none_description_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-45 — an explicit null description is blank -> 400, nothing written
    (best-practice default, delegated by reviewer).
    Rules: update_expense_order R2, R12 [BUG-753]."""
    o = uo(O, f1, a1)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, description=None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    r = reread_order(db, o.id)
    assert r.description == "Rent March"
    assert r.updated_by is None
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no exception (returns O, updated_by == U2)")
def test_eo_u_46__bug_753_all_null_payload_on_completed_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-46 — an all-null payload still counts as present on a completed
    order -> 400, nothing written (best-practice default, delegated by reviewer).
    Rules: update_expense_order R3 [BUG-753]."""
    o = uo(O, f1, a1, completed_at=T0)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, due_date=None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete and cannot be edited"
    r = reread_order(db, o.id)
    assert r.due_date == date(2026, 3, 31)
    assert r.updated_by is None
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_753 + " — fails today on: no exception (returns O)")
def test_eo_u_47__bug_753_all_null_payload_on_voided_rejected(db, M, w1, O, f1, a1, u2):
    """EO-U-47 — an all-null payload still counts as present on a voided order
    -> 400, nothing written (best-practice default, delegated by reviewer).
    Rules: update_expense_order R3 [BUG-753] [BUG-754]."""
    o = uo(O, f1, a1, voided=True)
    with pytest.raises(HTTPException) as exc:
        call_u(db, M, o, w1, u2, due_date=None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    r = reread_order(db, o.id)
    assert r.due_date == date(2026, 3, 31)
    assert r.updated_by is None
    assert events_of(db, o.id) == []


def _reset_case(db, M, w1, O, f1, a1, u2, u3, approver_factory, **payload):
    """Shared body of U-48..U-51: O with U3 approved and U2 pending; applies a
    single-field update and returns (result, order)."""
    o = uo(O, f1, a1)
    approver_factory(o, u3, assigned_by=u2, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u2, approved=False)
    result = call_u(db, M, o, w1, u2, **payload)
    return result, o


def _assert_reset_ok(db, result, o, u2, u3):
    assert result.id == o.id
    assert result._approvals_reset is True
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    assert approver_row(db, o.id, u2.id).approved is False
    events = events_of(db, o.id)
    assert events[0].event_type == "approvals_reset"
    assert events[0].description == "Order details edited (1 approval(s) cleared)"
    assert events[0].performed_by == u2.id
    return events


def test_eo_u_48__account_change_resets_approvals(db, M, w1, O, f1, a1, a2, u2, u3, approver_factory):
    """EO-U-48 — changing only account_id resets recorded approvals.
    Rules: update_expense_order R9, R11."""
    result, o = _reset_case(db, M, w1, O, f1, a1, u2, u3, approver_factory, account_id=a2.id)
    r = reread_order(db, o.id)
    assert r.account_id == a2.id
    assert r.expense_category == "factory" and r.cost_center_id == f1.id
    assert r.expense_date == date(2026, 3, 1) and r.due_date == date(2026, 3, 31)
    assert r.description == "Rent March"
    events = _assert_reset_ok(db, result, o, u2, u3)
    assert [(e.event_type, e.description) for e in events] == [
        ("approvals_reset", "Order details edited (1 approval(s) cleared)"),
        ("updated", "Order details updated"),
    ]
    assert events[1].performed_by == u2.id


def test_eo_u_49__category_change_resets_approvals(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-49 — changing only expense_category (factory -> other) resets
    recorded approvals. cost_center_id and the exact `changes` list are not
    asserted (BUG-752).
    Rules: update_expense_order R9, R11."""
    result, o = _reset_case(db, M, w1, O, f1, a1, u2, u3, approver_factory, expense_category="other")
    r = reread_order(db, o.id)
    assert r.expense_category == "other"
    assert r.account_id == a1.id
    assert r.expense_date == date(2026, 3, 1) and r.due_date == date(2026, 3, 31)
    assert r.description == "Rent March"
    events = _assert_reset_ok(db, result, o, u2, u3)
    assert [e.event_type for e in events] == ["approvals_reset", "updated"]


def test_eo_u_50__cost_center_change_resets_approvals(db, M, w1, O, f1, f3, a1, u2, u3, approver_factory):
    """EO-U-50 — changing only cost_center_id (F1 -> F3) resets recorded approvals.
    Rules: update_expense_order R9, R11."""
    result, o = _reset_case(db, M, w1, O, f1, a1, u2, u3, approver_factory, cost_center_id=f3.id)
    r = reread_order(db, o.id)
    assert r.cost_center_id == f3.id
    assert r.expense_category == "factory" and r.account_id == a1.id
    assert r.expense_date == date(2026, 3, 1) and r.due_date == date(2026, 3, 31)
    assert r.description == "Rent March"
    events = _assert_reset_ok(db, result, o, u2, u3)
    assert [(e.event_type, e.description) for e in events] == [
        ("approvals_reset", "Order details edited (1 approval(s) cleared)"),
        ("updated", "Order details updated"),
    ]


def test_eo_u_51__due_date_change_resets_approvals(db, M, w1, O, f1, a1, u2, u3, approver_factory):
    """EO-U-51 — changing only due_date resets recorded approvals.
    Rules: update_expense_order R9, R11."""
    result, o = _reset_case(db, M, w1, O, f1, a1, u2, u3, approver_factory, due_date=date(2026, 4, 15))
    r = reread_order(db, o.id)
    assert r.due_date == date(2026, 4, 15)
    assert r.account_id == a1.id and r.expense_category == "factory" and r.cost_center_id == f1.id
    assert r.expense_date == date(2026, 3, 1)
    assert r.description == "Rent March"
    events = _assert_reset_ok(db, result, o, u2, u3)
    assert [(e.event_type, e.description) for e in events] == [
        ("approvals_reset", "Order details edited (1 approval(s) cleared)"),
        ("updated", "Order details updated"),
    ]


# --------------------------------------------------------------------------- #
# `get_expense_order`
# --------------------------------------------------------------------------- #

def test_eo_g_01__returns_order(db, M, w1, O):
    """EO-G-01 — returns the order by id and workspace.
    Rules: get_expense_order R1."""
    o = O()
    result = M.get_expense_order(db, o.id, w1.id)
    assert result.id == o.id
    assert result.expense_number == "EXP-2000-101"


def test_eo_g_02__voided_and_completed_still_returned(db, M, w1, O):
    """EO-G-02 — a voided and completed order is still returned.
    Rules: get_expense_order R1 (soft-delete)."""
    o = O(voided=True, completed_at=T0)
    result = M.get_expense_order(db, o.id, w1.id)
    assert result.id == o.id


def test_eo_g_03__missing_order_404(db, M, w1, O):
    """EO-G-03 — a missing order id -> 404.
    Rules: get_expense_order R2."""
    O()
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.get_expense_order(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)


def test_eo_g_04__other_workspace_order_404(db, M, w1, O5):
    """EO-G-04 — an order of another workspace -> 404.
    Rules: get_expense_order R2 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M.get_expense_order(db, O5.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)


# --------------------------------------------------------------------------- #
# Hub fixture H and shared hub helpers
# --------------------------------------------------------------------------- #

ALL = dict(exclude_complete=False, exclude_voided=False)


def mk_account(db, ws, user, name):
    row = Account(workspace_id=ws.id, name=name, is_active=True, is_deleted=False, created_by=user.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def H(db, w1, w2, order_factory, u1, u4, f1, d1, a1, a2, aw2, f2, invoice_factory):
    """Convention 'Hub fixture H'. Rows inserted in order O1..O5."""
    o1 = order_factory(
        w1, u1, expense_category="factory", cost_center_id=f1.id, account_id=a1.id,
        expense_date=date(2026, 3, 1), subtotal=Decimal("100.00"), total_amount=Decimal("100.00"),
    )
    o2 = order_factory(
        w1, u1, expense_category="department", cost_center_id=d1.id, account_id=None,
        expense_date=date(2026, 3, 5), subtotal=Decimal("200.00"), total_amount=Decimal("200.00"),
    )
    i2 = invoice_factory(
        w1, a1, invoice_status="draft", payment_status="unpaid",
        invoice_amount=Decimal("200.00"), paid_amount=Decimal("0"), order_id=o2.id,
    )
    o2.invoice_id = i2.id
    db.flush()
    o3 = order_factory(
        w1, u1, expense_category="other", cost_center_id=None, account_id=a2.id,
        expense_date=date(2026, 3, 10), subtotal=Decimal("300.00"), total_amount=Decimal("300.00"),
        completed_at=T0,
    )
    i3 = invoice_factory(
        w1, a2, invoice_status="confirmed", payment_status="paid",
        invoice_amount=Decimal("300.00"), paid_amount=Decimal("300.00"), order_id=o3.id,
    )
    o3.invoice_id = i3.id
    db.flush()
    o4 = order_factory(
        w1, u1, expense_category="factory", cost_center_id=f1.id, account_id=a1.id,
        expense_date=date(2026, 3, 15), subtotal=Decimal("400.00"), total_amount=Decimal("400.00"),
        voided=True,
    )
    o5 = order_factory(
        w2, u4, expense_category="factory", cost_center_id=f2.id, account_id=aw2.id,
        expense_date=date(2026, 3, 5), subtotal=Decimal("500.00"), total_amount=Decimal("500.00"),
    )
    return SimpleNamespace(o1=o1, o2=o2, o3=o3, o4=o4, o5=o5, i2=i2, i3=i3)


def hub_ids(db, M, ws_id, **kw):
    return [o.id for o in M.list_expense_orders_for_hub(db, ws_id, **kw)]


# --------------------------------------------------------------------------- #
# `list_expense_orders_for_hub`
# --------------------------------------------------------------------------- #

def test_eo_hl_01__default_excludes_complete_and_voided(db, M, w1, H):
    """EO-HL-01 -- defaults exclude complete and voided.
    Rules: list_expense_orders_for_hub R1, R7, R8, R12."""
    assert hub_ids(db, M, w1.id) == [H.o2.id, H.o1.id]


def test_eo_hl_02__all_includes_everything(db, M, w1, H):
    """EO-HL-02 -- ALL includes complete and voided.
    Rules: R7, R8, R12."""
    assert hub_ids(db, M, w1.id, **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_03__workspace_isolation(db, M, w2, H):
    """EO-HL-03 -- listing W2 returns only W2's orders.
    Rules: R1 (isolation)."""
    assert hub_ids(db, M, w2.id) == [H.o5.id]


def test_eo_hl_04__exclude_voided_false(db, M, w1, H):
    """EO-HL-04 -- exclude_voided=False keeps voided, complete still excluded.
    Rules: R7 (boundary)."""
    assert hub_ids(db, M, w1.id, exclude_voided=False) == [H.o4.id, H.o2.id, H.o1.id]


def test_eo_hl_05__exclude_complete_false(db, M, w1, H):
    """EO-HL-05 -- exclude_complete=False keeps complete, voided still excluded.
    Rules: R8 (boundary)."""
    assert hub_ids(db, M, w1.id, exclude_complete=False) == [H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_06__category_filter(db, M, w1, H):
    """EO-HL-06 -- expense_category filter.
    Rules: R2 (happy)."""
    assert hub_ids(db, M, w1.id, expense_category="factory", **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_07__category_empty_string_ignored(db, M, w1, H):
    """EO-HL-07 -- empty category -> no filter.
    Rules: R2 (boundary)."""
    assert hub_ids(db, M, w1.id, expense_category="", **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_08__category_none_ignored(db, M, w1, H):
    """EO-HL-08 -- category=None -> no filter.
    Rules: R2 (boundary)."""
    assert hub_ids(db, M, w1.id, expense_category=None, **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_09__account_filter(db, M, w1, H, a1):
    """EO-HL-09 -- account_id filter.
    Rules: R3 (happy)."""
    assert hub_ids(db, M, w1.id, account_id=a1.id, **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_10__account_zero_no_match(db, M, w1, H):
    """EO-HL-10 -- account_id=0 matches nothing.
    Rules: R3 (boundary)."""
    assert hub_ids(db, M, w1.id, account_id=0, **ALL) == []


def test_eo_hl_11__invoice_filter(db, M, w1, H):
    """EO-HL-11 -- invoice_id filter.
    Rules: R3 (happy)."""
    assert hub_ids(db, M, w1.id, invoice_id=H.i2.id, **ALL) == [H.o2.id]


def test_eo_hl_12__invoice_zero_no_match(db, M, w1, H):
    """EO-HL-12 -- invoice_id=0 matches nothing.
    Rules: R3 (boundary)."""
    assert hub_ids(db, M, w1.id, invoice_id=0, **ALL) == []


def test_eo_hl_13__date_range_both_ends(db, M, w1, H):
    """EO-HL-13 -- date_from/date_to inclusive on both ends.
    Rules: R4 (boundary)."""
    assert hub_ids(db, M, w1.id, date_from=date(2026, 3, 5), date_to=date(2026, 3, 10), **ALL) == [H.o3.id, H.o2.id]


def test_eo_hl_14__date_range_empty(db, M, w1, H):
    """EO-HL-14 -- a date range with nothing inside -> [].
    Rules: R4 (boundary)."""
    assert hub_ids(db, M, w1.id, date_from=date(2026, 3, 6), date_to=date(2026, 3, 9), **ALL) == []


def test_eo_hl_15__date_from_only(db, M, w1, H):
    """EO-HL-15 -- date_from only.
    Rules: R4 (boundary)."""
    assert hub_ids(db, M, w1.id, date_from=date(2026, 3, 10), **ALL) == [H.o4.id, H.o3.id]


def test_eo_hl_16__date_to_only(db, M, w1, H):
    """EO-HL-16 -- date_to only.
    Rules: R4 (boundary)."""
    assert hub_ids(db, M, w1.id, date_to=date(2026, 3, 1), **ALL) == [H.o1.id]


def test_eo_hl_17__status_draft(db, M, w1, H):
    """EO-HL-17 -- status_ids=[1] (draft).
    Rules: R5 (happy)."""
    assert hub_ids(db, M, w1.id, status_ids=[1], **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_18__status_invoiced(db, M, w1, H):
    """EO-HL-18 -- status_ids=[2] (invoiced).
    Rules: R5 (happy)."""
    assert hub_ids(db, M, w1.id, status_ids=[2], **ALL) == [H.o2.id]


def test_eo_hl_19__status_complete(db, M, w1, H):
    """EO-HL-19 -- status_ids=[3] (complete).
    Rules: R5 (happy)."""
    assert hub_ids(db, M, w1.id, status_ids=[3], **ALL) == [H.o3.id]


def test_eo_hl_20__status_multiple(db, M, w1, H):
    """EO-HL-20 -- status_ids=[1, 3].
    Rules: R5 (boundary)."""
    assert hub_ids(db, M, w1.id, status_ids=[1, 3], **ALL) == [H.o4.id, H.o3.id, H.o1.id]


def test_eo_hl_21__status_unknown_only_no_filter(db, M, w1, H):
    """EO-HL-21 -- an unknown status id alone -> no stage filter applied.
    Rules: R5 (boundary)."""
    assert hub_ids(db, M, w1.id, status_ids=[99], **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_22__status_known_plus_unknown(db, M, w1, H):
    """EO-HL-22 -- a known status id plus an unknown one -> unknown ignored.
    Rules: R5 (boundary)."""
    assert hub_ids(db, M, w1.id, status_ids=[2, 99], **ALL) == [H.o2.id]


def test_eo_hl_23__status_empty_list_no_filter(db, M, w1, H):
    """EO-HL-23 -- status_ids=[] -> no filter.
    Rules: R5 (boundary)."""
    assert hub_ids(db, M, w1.id, status_ids=[], **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_24__invoice_filter_invoiced(db, M, w1, H):
    """EO-HL-24 -- invoice_filter='invoiced'.
    Rules: R6 (happy)."""
    assert hub_ids(db, M, w1.id, invoice_filter="invoiced", **ALL) == [H.o3.id, H.o2.id]


def test_eo_hl_25__invoice_filter_not_invoiced(db, M, w1, H):
    """EO-HL-25 -- invoice_filter='not_invoiced'.
    Rules: R6 (happy)."""
    assert hub_ids(db, M, w1.id, invoice_filter="not_invoiced", **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_26__invoice_filter_bogus_ignored(db, M, w1, H):
    """EO-HL-26 -- an unrecognized invoice_filter value -> no filter.
    Rules: R6 (boundary)."""
    assert hub_ids(db, M, w1.id, invoice_filter="bogus", **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_27__search_account_name_middle_case_insensitive(db, M, w1, H):
    """EO-HL-27 -- search matches the middle of an account name, case-insensitive.
    Rules: R9 (happy)."""
    assert hub_ids(db, M, w1.id, search="CME S", **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_28__search_number_middle(db, M, w1, H):
    """EO-HL-28 -- search matches the middle of an expense number; an order
    with no account still matches.
    Rules: R9 (happy)."""
    assert hub_ids(db, M, w1.id, search="0-102", **ALL) == [H.o2.id]


def test_eo_hl_29__search_category_label(db, M, w1, H):
    """EO-HL-29 -- search matches a category label.
    Rules: R9 (happy)."""
    assert hub_ids(db, M, w1.id, search="ACTOR", **ALL) == [H.o4.id, H.o1.id]


def test_eo_hl_30__search_category_label_department(db, M, w1, H):
    """EO-HL-30 -- search matches the 'Department' category label.
    Rules: R9 (happy)."""
    assert hub_ids(db, M, w1.id, search="Depart", **ALL) == [H.o2.id]


def test_eo_hl_31__search_whitespace_only_ignored(db, M, w1, H):
    """EO-HL-31 -- whitespace-only search -> no filter.
    Rules: R9 (boundary)."""
    assert hub_ids(db, M, w1.id, search="   ", **ALL) == [H.o4.id, H.o3.id, H.o2.id, H.o1.id]


def test_eo_hl_32__search_empty_and_none_ignored(db, M, w1, H):
    """EO-HL-32 -- empty string and None search both -> no filter.
    Rules: R9 (boundary)."""
    expected = [H.o4.id, H.o3.id, H.o2.id, H.o1.id]
    assert hub_ids(db, M, w1.id, search="", **ALL) == expected
    assert hub_ids(db, M, w1.id, search=None, **ALL) == expected


def test_eo_hl_33__search_trimmed(db, M, w1, H):
    """EO-HL-33 -- leading/trailing whitespace in search is trimmed.
    Rules: R9 (boundary)."""
    assert hub_ids(db, M, w1.id, search="  beta tr  ", **ALL) == [H.o3.id]


def test_eo_hl_34__search_no_match(db, M, w1, H):
    """EO-HL-34 -- a search term matching nothing -> [].
    Rules: R9 (boundary)."""
    assert hub_ids(db, M, w1.id, search="zzz", **ALL) == []


def test_eo_hl_35__filters_combine_with_and(db, M, w1, H, a1):
    """EO-HL-35 -- multiple filters combine with AND.
    Rules: R10 (happy)."""
    assert hub_ids(
        db, M, w1.id, expense_category="factory", account_id=a1.id, date_to=date(2026, 3, 10), **ALL
    ) == [H.o1.id]


def test_eo_hl_36__default_exclusions_apply_before_search(db, M, w1, H):
    """EO-HL-36 -- default exclusions apply before the search narrows further.
    Rules: R10 (boundary)."""
    assert hub_ids(db, M, w1.id, search="CME S") == [H.o1.id]


@pytest.fixture
def search_accounts_orders(db, w1, u1, order_factory):
    """Convention fixture for HL-37..39 / HC-07 / HR-07 -- P1, P2, P3."""
    a_100 = mk_account(db, w1, u1, "100% Parts")
    a_ab = mk_account(db, w1, u1, "A_B Traders")
    a_plain = mk_account(db, w1, u1, "Plain Co")
    p1 = order_factory(w1, u1, account_id=a_100.id, expense_date=date(2026, 3, 1))
    p2 = order_factory(w1, u1, account_id=a_ab.id, expense_date=date(2026, 3, 1))
    p3 = order_factory(w1, u1, account_id=a_plain.id, expense_date=date(2026, 3, 1))
    return SimpleNamespace(p1=p1, p2=p2, p3=p3)


def test_eo_hl_37__search_percent_literal_in_account_name(db, M, w1, search_accounts_orders):
    """EO-HL-37 -- search text containing a literal percent sign matches it
    literally when it is actually present in the data.
    Rules: R11 (happy)."""
    assert hub_ids(db, M, w1.id, search="0% P", **ALL) == [search_accounts_orders.p1.id]


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: returns all three")
def test_eo_hl_38__bug_745_percent_wildcard_not_escaped(db, M, w1, search_accounts_orders):
    """EO-HL-38 -- a bare percent sign should match only accounts containing a
    literal percent sign, not act as an ILIKE wildcard over everything.
    Rules: R11 [BUG-745]."""
    assert hub_ids(db, M, w1.id, search="%", **ALL) == [search_accounts_orders.p1.id]


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: returns all three")
def test_eo_hl_39__bug_745_underscore_wildcard_not_escaped(db, M, w1, search_accounts_orders):
    """EO-HL-39 -- a bare underscore should match only accounts containing a
    literal underscore, not act as an ILIKE single-char wildcard over everything.
    Rules: R11 [BUG-745]."""
    assert hub_ids(db, M, w1.id, search="_", **ALL) == [search_accounts_orders.p2.id]


@pytest.fixture
def ordering_orders(db, w1, u1, order_factory):
    """Convention fixture for HL-40/41 -- Q1..Q4 with date/created_at ties."""
    q1 = order_factory(w1, u1, expense_date=date(2026, 3, 1), created_at=T0)
    q2 = order_factory(w1, u1, expense_date=date(2026, 3, 1), created_at=T0 + timedelta(hours=1))
    q3 = order_factory(w1, u1, expense_date=date(2026, 3, 1), created_at=T0 + timedelta(hours=1))
    q4 = order_factory(w1, u1, expense_date=date(2026, 3, 2), created_at=T0)
    return SimpleNamespace(q1=q1, q2=q2, q3=q3, q4=q4)


def test_eo_hl_40__hub_ordering_date_then_created_then_id(db, M, w1, ordering_orders):
    """EO-HL-40 -- hub ordering: expense_date desc, created_at desc, id desc.
    Rules: R12 (boundary)."""
    o = ordering_orders
    assert hub_ids(db, M, w1.id) == [o.q4.id, o.q3.id, o.q2.id, o.q1.id]


def test_eo_hl_41__skip_and_limit(db, M, w1, ordering_orders):
    """EO-HL-41 -- skip/limit paginate the ordered list.
    Rules: R12 (boundary)."""
    o = ordering_orders
    assert hub_ids(db, M, w1.id, skip=1, limit=2) == [o.q3.id, o.q2.id]


def test_eo_hl_42__default_limit_is_50(db, M, w1, order_factory, u1):
    """EO-HL-42 -- the default limit caps the hub listing at 50.
    Rules: R12 (boundary)."""
    orders = [order_factory(w1, u1, expense_date=date(2026, 3, 1), created_at=T0) for _ in range(51)]
    ids = hub_ids(db, M, w1.id)
    assert len(ids) == 50
    assert ids == sorted((o.id for o in orders), reverse=True)[:50]


def test_eo_hl_43__unknown_kwarg_raises_typeerror(db, M, w1, H):
    """EO-HL-43 -- an unrecognized filter kwarg raises TypeError.
    Rules: Errors."""
    with pytest.raises(TypeError):
        M.list_expense_orders_for_hub(db, w1.id, foo=1)


def test_eo_hl_44__status_filter_respects_default_exclusions(db, M, w1, H):
    """EO-HL-44 -- defaults exclude voided even under a status filter.
    Rules: R5, R7 (boundary)."""
    assert hub_ids(db, M, w1.id, status_ids=[1]) == [H.o1.id]


@pytest.fixture
def backslash_orders(db, w1, u1, order_factory):
    """Convention fixture for HL-45/46 -- B1 (account name has a literal
    backslash), B2 (plain)."""
    acme_bs = mk_account(db, w1, u1, "Acme" + chr(92) + "Ltd")
    acme_plain = mk_account(db, w1, u1, "AcmeLtd")
    b1 = order_factory(w1, u1, account_id=acme_bs.id, expense_date=date(2026, 3, 1))
    b2 = order_factory(w1, u1, account_id=acme_plain.id, expense_date=date(2026, 3, 1))
    return SimpleNamespace(b1=b1, b2=b2)


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: returns [B2]")
def test_eo_hl_45__bug_745_backslash_not_escaped(db, M, w1, backslash_orders):
    """EO-HL-45 -- a literal backslash in the search text should match the
    account containing it, not be eaten by ILIKE escaping rules.
    Rules: R11 [BUG-745]."""
    assert hub_ids(db, M, w1.id, search="Acme" + chr(92) + "Ltd", **ALL) == [backslash_orders.b1.id]


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: returns []")
def test_eo_hl_46__bug_745_trailing_backslash_not_escaped(db, M, w1, backslash_orders):
    """EO-HL-46 -- a trailing literal backslash should still match.
    Rules: R11 [BUG-745]."""
    assert hub_ids(db, M, w1.id, search="Acme" + chr(92), **ALL) == [backslash_orders.b1.id]


# --------------------------------------------------------------------------- #
# `count_expense_orders_for_hub`
# --------------------------------------------------------------------------- #

def test_eo_hc_01__count_default(db, M, w1, H):
    """EO-HC-01 -- default count excludes complete/voided.
    Rules: count_expense_orders_for_hub R1 (happy)."""
    assert M.count_expense_orders_for_hub(db, w1.id) == 2


def test_eo_hc_02__count_all(db, M, w1, H):
    """EO-HC-02 -- ALL counts everything.
    Rules: R1 (boundary)."""
    assert M.count_expense_orders_for_hub(db, w1.id, **ALL) == 4


def test_eo_hc_03__count_isolation(db, M, w2, H):
    """EO-HC-03 -- counting W2 only counts W2's orders.
    Rules: R1 (isolation)."""
    assert M.count_expense_orders_for_hub(db, w2.id) == 1


def test_eo_hc_04__count_search_no_match(db, M, w1, H):
    """EO-HC-04 -- a search term matching nothing -> 0.
    Rules: R1 (boundary)."""
    assert M.count_expense_orders_for_hub(db, w1.id, search="zzz", **ALL) == 0


def test_eo_hc_05__count_no_paging(db, M, w1, order_factory, u1):
    """EO-HC-05 -- count is not paged, unlike the list.
    Rules: R1 (boundary)."""
    for _ in range(51):
        order_factory(w1, u1, expense_date=date(2026, 3, 1), created_at=T0)
    assert M.count_expense_orders_for_hub(db, w1.id) == 51


def test_eo_hc_06__count_combined_filters(db, M, w1, H):
    """EO-HC-06 -- search combined with invoice_filter.
    Rules: R1 (happy)."""
    assert M.count_expense_orders_for_hub(db, w1.id, search="CME S", invoice_filter="not_invoiced", **ALL) == 2


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: 3")
def test_eo_hc_07__bug_745_percent_wildcard_not_escaped(db, M, w1, search_accounts_orders):
    """EO-HC-07 -- a bare percent sign should count only accounts containing
    a literal percent sign.
    Rules: R1 [BUG-745]."""
    assert M.count_expense_orders_for_hub(db, w1.id, search="%", **ALL) == 1


def test_eo_hc_08__unknown_kwarg_raises_typeerror(db, M, w1, H):
    """EO-HC-08 -- an unrecognized filter kwarg raises TypeError.
    Rules: Errors."""
    with pytest.raises(TypeError):
        M.count_expense_orders_for_hub(db, w1.id, foo=1)


def test_eo_hc_09__count_zero_is_int(db, M, w1):
    """EO-HC-09 -- no orders -> 0 (an int, not None).
    Rules: R1 (boundary)."""
    result = M.count_expense_orders_for_hub(db, w1.id)
    assert result == 0
    assert isinstance(result, int)


# --------------------------------------------------------------------------- #
# `expense_order_hub_stats`
# --------------------------------------------------------------------------- #

def test_eo_hs_01__stats_default(db, M, w1, H):
    """EO-HS-01 -- default stats exclude complete/voided.
    Rules: expense_order_hub_stats R1-R3 (happy)."""
    assert M.expense_order_hub_stats(db, w1.id) == (2, Decimal("300.00"), 2, Decimal("300.00"), 1)


def test_eo_hs_02__stats_all(db, M, w1, H):
    """EO-HS-02 -- ALL stats across every order.
    Rules: R1-R3 (boundary)."""
    assert M.expense_order_hub_stats(db, w1.id, **ALL) == (4, Decimal("1000.00"), 3, Decimal("700.00"), 2)


def test_eo_hs_03__stats_isolation(db, M, w2, H):
    """EO-HS-03 -- stats for W2 only include W2's orders.
    Rules: R1 (isolation)."""
    assert M.expense_order_hub_stats(db, w2.id) == (1, Decimal("500.00"), 1, Decimal("500.00"), 1)


def test_eo_hs_04__stats_search_no_match(db, M, w1, H):
    """EO-HS-04 -- a search term matching nothing -> all zeros.
    Rules: R4 (boundary)."""
    assert M.expense_order_hub_stats(db, w1.id, search="zzz", **ALL) == (
        0, Decimal("0"), 0, Decimal("0"), 0,
    )


def test_eo_hs_05__stats_status_filter(db, M, w1, H):
    """EO-HS-05 -- a status filter narrows the stats.
    Rules: R2 (boundary)."""
    assert M.expense_order_hub_stats(db, w1.id, status_ids=[3], **ALL) == (
        1, Decimal("300.00"), 0, Decimal("0"), 0,
    )


def test_eo_hs_06__unknown_kwarg_raises_typeerror(db, M, w1, H):
    """EO-HS-06 -- an unrecognized filter kwarg raises TypeError.
    Rules: Errors."""
    with pytest.raises(TypeError):
        M.expense_order_hub_stats(db, w1.id, foo=1)


# --------------------------------------------------------------------------- #
# `list_expense_orders_recent_for_hub`
# --------------------------------------------------------------------------- #

def recent_ids(db, M, ws_id, **kw):
    return [o.id for o in M.list_expense_orders_recent_for_hub(db, ws_id, **kw)]


def test_eo_hr_01__default_limit_10(db, M, w1, order_factory, u1):
    """EO-HR-01 -- the default limit caps the recent listing at 10, newest first.
    Rules: list_expense_orders_recent_for_hub R1 (boundary)."""
    orders = []
    for n in range(1, 12):
        orders.append(order_factory(w1, u1, updated_at=T0 + timedelta(minutes=n)))
    ids = recent_ids(db, M, w1.id)
    assert ids == [orders[n - 1].id for n in range(11, 1, -1)]


def test_eo_hr_02__explicit_limit(db, M, w1, order_factory, u1):
    """EO-HR-02 -- an explicit limit further narrows the recent listing.
    Rules: R1 (boundary)."""
    orders = []
    for n in range(1, 12):
        orders.append(order_factory(w1, u1, updated_at=T0 + timedelta(minutes=n)))
    assert recent_ids(db, M, w1.id, limit=2) == [orders[10].id, orders[9].id]


def test_eo_hr_03__default_excludes_complete_and_voided(db, M, w1, H):
    """EO-HR-03 -- recent listing excludes complete and voided by default.
    Rules: R1 (happy)."""
    H.o1.updated_at = T0 + timedelta(hours=1)
    H.o2.updated_at = T0 + timedelta(hours=2)
    H.o4.updated_at = T0 + timedelta(hours=4)
    db.flush()
    assert recent_ids(db, M, w1.id) == [H.o2.id, H.o1.id]


def test_eo_hr_04__isolation(db, M, w2, H):
    """EO-HR-04 -- recent listing for W2 only includes W2's orders.
    Rules: R1 (isolation)."""
    H.o1.updated_at = T0 + timedelta(hours=1)
    H.o2.updated_at = T0 + timedelta(hours=2)
    H.o4.updated_at = T0 + timedelta(hours=4)
    db.flush()
    assert recent_ids(db, M, w2.id) == [H.o5.id]


def test_eo_hr_05__sorted_by_updated_at_desc(db, M, w1, order_factory, u1):
    """EO-HR-05 -- more recently updated orders come first.
    Rules: R2 (happy)."""
    a = order_factory(w1, u1, created_at=T0, updated_at=T0 + timedelta(days=2))
    b = order_factory(w1, u1, created_at=T0, updated_at=T0 + timedelta(days=1))
    assert recent_ids(db, M, w1.id) == [a.id, b.id]


@pytest.mark.xfail(strict=True, reason=BUG_746 + " -- fails today on: first element is not A (never-updated orders sort first)")
def test_eo_hr_06__bug_746_never_updated_sorts_first(db, M, w1, order_factory, u1):
    """EO-HR-06 -- never-updated orders should not outrank recently-updated ones.
    Rules: R2 [BUG-746]."""
    a = order_factory(w1, u1, created_at=datetime(2026, 3, 1, 9, 0, 0), updated_at=datetime(2026, 3, 20, 9, 0, 0))
    b = order_factory(w1, u1, created_at=datetime(2026, 3, 10, 9, 0, 0), updated_at=None)
    c = order_factory(w1, u1, created_at=datetime(2026, 3, 15, 9, 0, 0), updated_at=None)
    d = order_factory(w1, u1, created_at=datetime(2026, 3, 15, 9, 0, 0), updated_at=None)
    assert d.id > c.id
    assert recent_ids(db, M, w1.id) == [a.id, d.id, c.id, b.id]


@pytest.mark.xfail(strict=True, reason=BUG_745 + " -- fails today on: returns all three")
def test_eo_hr_07__bug_745_underscore_wildcard_not_escaped(db, M, w1, search_accounts_orders):
    """EO-HR-07 -- a bare underscore should match only the account containing
    a literal underscore.
    Rules: R1 [BUG-745]."""
    assert recent_ids(db, M, w1.id, search="_", **ALL) == [search_accounts_orders.p2.id]


def test_eo_hr_08__unknown_kwarg_raises_typeerror(db, M, w1, H):
    """EO-HR-08 -- an unrecognized filter kwarg raises TypeError.
    Rules: Errors."""
    with pytest.raises(TypeError):
        M.list_expense_orders_recent_for_hub(db, w1.id, foo=1)


# --------------------------------------------------------------------------- #
# `expense_order_financial_snapshot`
# --------------------------------------------------------------------------- #

@contextmanager
def patched_now(dt):
    """Convention 'Time' override for FN cases that need a NOW other than the
    module default."""
    with patch("app.dao.expense_order.utcnow", return_value=dt):
        yield


def fn(db, M, ws_id, **filters):
    return M.expense_order_financial_snapshot(db, ws_id, **filters)


def cat_e(key, label, count, total):
    return {"key": key, "label": label, "count": count, "total_value": total}


def stage_e(key, label, count, total):
    return {"key": key, "label": label, "count": count, "total_value": total}


def acct_e(account_id, name, count, total):
    return {"account_id": account_id, "account_name": name, "count": count, "total_value": total}


def test_eo_fn_01__category_breakdown_default(db, M, w1, H):
    """EO-FN-01 -- category breakdown, default scope, sorted by value desc.
    Rules: expense_order_financial_snapshot R1 (happy)."""
    result = fn(db, M, w1.id)
    assert result["category_breakdown"] == [
        cat_e("department", "Department", 1, Decimal("200.00")),
        cat_e("factory", "Factory", 1, Decimal("100.00")),
    ]


def test_eo_fn_02__category_breakdown_all(db, M, w1, H):
    """EO-FN-02 -- category breakdown, ALL scope.
    Rules: R1 (boundary)."""
    result = fn(db, M, w1.id, **ALL)
    assert result["category_breakdown"] == [
        cat_e("factory", "Factory", 2, Decimal("500.00")),
        cat_e("other", "Other", 1, Decimal("300.00")),
        cat_e("department", "Department", 1, Decimal("200.00")),
    ]


def test_eo_fn_03__category_label_title_cased_fallback(db, M, w1, order_factory, u1):
    """EO-FN-03 -- a category outside the known labels falls back to a
    title-cased label.
    Rules: R1 (boundary)."""
    order_factory(
        w1, u1, expense_category="office_supplies", cost_center_id=None,
        subtotal=Decimal("50.00"), total_amount=Decimal("50.00"),
    )
    result = fn(db, M, w1.id)
    assert result["category_breakdown"] == [cat_e("office_supplies", "Office Supplies", 1, Decimal("50.00"))]


def test_eo_fn_04__search_no_match_empty_breakdowns(db, M, w1, H):
    """EO-FN-04 -- a search term matching nothing empties the breakdowns.
    Rules: R2 (boundary)."""
    result = fn(db, M, w1.id, search="zzz", **ALL)
    assert result["category_breakdown"] == []
    assert result["open_by_account"] == []


def test_eo_fn_05__stage_pipeline_all(db, M, w1, H):
    """EO-FN-05 -- stage pipeline, ALL scope; a voided order still counts
    toward its stage (draft here).
    Rules: R3 (happy)."""
    result = fn(db, M, w1.id, **ALL)
    assert result["stage_pipeline"] == [
        stage_e("draft", "Draft", 2, Decimal("500.00")),
        stage_e("invoiced", "Invoiced", 1, Decimal("200.00")),
        stage_e("complete", "Complete", 1, Decimal("300.00")),
    ]


def test_eo_fn_06__stage_pipeline_default(db, M, w1, H):
    """EO-FN-06 -- stage pipeline, default scope; an empty stage still appears
    with zero count/value.
    Rules: R3 (boundary)."""
    result = fn(db, M, w1.id)
    assert result["stage_pipeline"] == [
        stage_e("draft", "Draft", 1, Decimal("100.00")),
        stage_e("invoiced", "Invoiced", 1, Decimal("200.00")),
        stage_e("complete", "Complete", 0, Decimal(0)),
    ]


def test_eo_fn_07__stage_pipeline_no_orders(db, M, w1):
    """EO-FN-07 -- no orders -> all three stages at zero.
    Rules: R3 (boundary)."""
    result = fn(db, M, w1.id)
    assert result["stage_pipeline"] == [
        stage_e("draft", "Draft", 0, Decimal(0)),
        stage_e("invoiced", "Invoiced", 0, Decimal(0)),
        stage_e("complete", "Complete", 0, Decimal(0)),
    ]


def test_eo_fn_08__open_by_account_default(db, M, w1, H, a1):
    """EO-FN-08 -- open-by-account, default scope; an order with no account
    is not listed.
    Rules: R4, R5 (happy)."""
    result = fn(db, M, w1.id)
    assert result["open_by_account"] == [acct_e(a1.id, "Acme Supplies", 1, Decimal("100.00"))]


def test_eo_fn_09__open_by_account_all_excludes_completed(db, M, w1, H, a1):
    """EO-FN-09 -- open-by-account, ALL scope; completed orders are still
    excluded from the open bucket.
    Rules: R4 (boundary)."""
    result = fn(db, M, w1.id, **ALL)
    assert result["open_by_account"] == [acct_e(a1.id, "Acme Supplies", 2, Decimal("500.00"))]


def test_eo_fn_10__open_by_account_top_5(db, M, w1, order_factory, u1):
    """EO-FN-10 -- open-by-account is capped at the top 5 accounts by value.
    Rules: R6 (boundary)."""
    totals = [Decimal("100.00"), Decimal("200.00"), Decimal("300.00"), Decimal("400.00"), Decimal("500.00"), Decimal("600.00")]
    for i, total in enumerate(totals, start=1):
        acc = mk_account(db, w1, u1, f"Account {i}")
        order_factory(w1, u1, account_id=acc.id, subtotal=total, total_amount=total)
    result = fn(db, M, w1.id)
    assert [e["total_value"] for e in result["open_by_account"]] == [
        Decimal("600.00"), Decimal("500.00"), Decimal("400.00"), Decimal("300.00"), Decimal("200.00"),
    ]


@pytest.mark.xfail(strict=True, reason=BUG_747 + " -- fails today on: tie order differs")
def test_eo_fn_11__bug_747_open_by_account_tie_order(db, M, w1, order_factory, u1):
    """EO-FN-11 -- ties in open-by-account value have no guaranteed order; the
    UI would want alphabetical.
    Rules: R6 [BUG-747]."""
    for name in ("delta", "Charlie", "bravo", "Alpha", "echo", "Foxtrot"):
        acc = mk_account(db, w1, u1, name)
        order_factory(w1, u1, account_id=acc.id, subtotal=Decimal("100.00"), total_amount=Decimal("100.00"))
    result = fn(db, M, w1.id)
    assert [e["account_name"] for e in result["open_by_account"]] == ["Alpha", "bravo", "Charlie", "delta", "echo"]


def test_eo_fn_12__due_timeline_buckets_and_filters_ignored(db, M, w1, w2, order_factory, u1, u4, f2):
    """EO-FN-12 -- due_timeline buckets by overdue/this-week/later-this-month/
    no-due-date; hub filters are ignored for the actionable part.
    Rules: R7, R8 (happy)."""
    with patched_now(NOW):
        q1 = order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("10"), total_amount=Decimal("10"))
        order_factory(w1, u1, due_date=date(2026, 3, 11), subtotal=Decimal("20"), total_amount=Decimal("20"))
        order_factory(w1, u1, due_date=date(2026, 3, 15), subtotal=Decimal("30"), total_amount=Decimal("30"))
        order_factory(w1, u1, due_date=date(2026, 3, 16), subtotal=Decimal("40"), total_amount=Decimal("40"))
        order_factory(w1, u1, due_date=date(2026, 3, 31), subtotal=Decimal("50"), total_amount=Decimal("50"))
        order_factory(w1, u1, due_date=date(2026, 4, 1), subtotal=Decimal("60"), total_amount=Decimal("60"))
        order_factory(w1, u1, due_date=None, subtotal=Decimal("70"), total_amount=Decimal("70"))
        order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("80"), total_amount=Decimal("80"), voided=True)
        order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("90"), total_amount=Decimal("90"), completed_at=T0)
        order_factory(w2, u4, cost_center_id=f2.id, due_date=date(2026, 3, 10), subtotal=Decimal("100"), total_amount=Decimal("100"))
        result = fn(db, M, w1.id, expense_category="department")
    timeline = result["due_timeline"]
    assert [b["key"] for b in timeline] == ["overdue", "due_this_week", "due_later_this_month", "no_due_date"]
    assert [b["label"] for b in timeline] == ["Overdue", "Due this week", "Due later this month", "No due date"]
    assert [(b["count"], b["total_value"]) for b in timeline] == [
        (1, Decimal("10.00")), (2, Decimal("50.00")), (2, Decimal("90.00")), (1, Decimal("70.00")),
    ]
    assert q1.due_date == date(2026, 3, 10)


def test_eo_fn_13__due_timeline_samples(db, M, w1, w2, order_factory, u1, u4, f2):
    """EO-FN-13 -- due_timeline carries up to 3 samples per bucket, ascending
    by due date. Given is "as FN-12": includes Q8 (voided), Q9 (completed) and
    Q10 (W2), all due 2026-03-10 (same day as Q1, which would land in the same
    "overdue" bucket if they were not excluded) -- verifier finding #4 (the
    previous pass omitted these three, so the exclusion was never exercised).
    Rules: R9 (side-effect)."""
    with patched_now(NOW):
        q1 = order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("10"), total_amount=Decimal("10"))
        q2 = order_factory(w1, u1, due_date=date(2026, 3, 11), subtotal=Decimal("20"), total_amount=Decimal("20"))
        q3 = order_factory(w1, u1, due_date=date(2026, 3, 15), subtotal=Decimal("30"), total_amount=Decimal("30"))
        q4 = order_factory(w1, u1, due_date=date(2026, 3, 16), subtotal=Decimal("40"), total_amount=Decimal("40"))
        q5 = order_factory(w1, u1, due_date=date(2026, 3, 31), subtotal=Decimal("50"), total_amount=Decimal("50"))
        order_factory(w1, u1, due_date=date(2026, 4, 1), subtotal=Decimal("60"), total_amount=Decimal("60"))
        q7 = order_factory(w1, u1, due_date=None, subtotal=Decimal("70"), total_amount=Decimal("70"))
        order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("80"), total_amount=Decimal("80"), voided=True)
        order_factory(w1, u1, due_date=date(2026, 3, 10), subtotal=Decimal("90"), total_amount=Decimal("90"), completed_at=T0)
        order_factory(w2, u4, cost_center_id=f2.id, due_date=date(2026, 3, 10), subtotal=Decimal("100"), total_amount=Decimal("100"))
        result = fn(db, M, w1.id)
    timeline = {b["key"]: b for b in result["due_timeline"]}
    assert timeline["overdue"]["count"] == 1
    assert timeline["overdue"]["samples"] == [
        {"id": q1.id, "order_number": q1.expense_number, "total_value": Decimal("10.00"), "sublabel": "2026-03-10"},
    ]
    assert timeline["due_this_week"]["samples"] == [
        {"id": q2.id, "order_number": q2.expense_number, "total_value": Decimal("20.00"), "sublabel": "2026-03-11"},
        {"id": q3.id, "order_number": q3.expense_number, "total_value": Decimal("30.00"), "sublabel": "2026-03-15"},
    ]
    assert timeline["due_later_this_month"]["samples"] == [
        {"id": q4.id, "order_number": q4.expense_number, "total_value": Decimal("40.00"), "sublabel": "2026-03-16"},
        {"id": q5.id, "order_number": q5.expense_number, "total_value": Decimal("50.00"), "sublabel": "2026-03-31"},
    ]
    assert timeline["no_due_date"]["count"] == 1
    assert timeline["no_due_date"]["samples"] == [
        {"id": q7.id, "order_number": q7.expense_number, "total_value": Decimal("70.00"), "sublabel": None},
    ]


def test_eo_fn_14__due_timeline_single_day_week(db, M, w1, order_factory, u1):
    """EO-FN-14 -- when end-of-week falls on NOW's own date, 'this week' is a
    single day.
    Rules: R8 (boundary)."""
    now = datetime(2026, 3, 15, 10, 0, 0)  # Sunday
    with patched_now(now):
        order_factory(w1, u1, due_date=date(2026, 3, 14), subtotal=Decimal("1"), total_amount=Decimal("1"))
        order_factory(w1, u1, due_date=date(2026, 3, 15), subtotal=Decimal("1"), total_amount=Decimal("1"))
        order_factory(w1, u1, due_date=date(2026, 3, 16), subtotal=Decimal("1"), total_amount=Decimal("1"))
        result = fn(db, M, w1.id)
    timeline = {b["key"]: b["count"] for b in result["due_timeline"]}
    assert timeline["overdue"] == 1
    assert timeline["due_this_week"] == 1
    assert timeline["due_later_this_month"] == 1


def test_eo_fn_15__due_timeline_sample_tiebreak_by_number(db, M, w1, order_factory, u1):
    """EO-FN-15 -- same-due-date ties are broken by expense_number ascending.
    Rules: R9 (boundary)."""
    with patched_now(NOW):
        order_factory(w1, u1, due_date=date(2026, 3, 8), expense_number="EXP-2000-101")
        s2 = order_factory(w1, u1, due_date=date(2026, 3, 5), expense_number="EXP-2000-103")
        s3 = order_factory(w1, u1, due_date=date(2026, 3, 5), expense_number="EXP-2000-102")
        s4 = order_factory(w1, u1, due_date=date(2026, 3, 1), expense_number="EXP-2000-104")
        n1 = order_factory(w1, u1, due_date=None, expense_number="EXP-2000-202")
        n2 = order_factory(w1, u1, due_date=None, expense_number="EXP-2000-201")
        n3 = order_factory(w1, u1, due_date=None, expense_number="EXP-2000-203")
        order_factory(w1, u1, due_date=None, expense_number="EXP-2000-204")
        result = fn(db, M, w1.id)
    timeline = {b["key"]: b for b in result["due_timeline"]}
    assert timeline["overdue"]["count"] == 4
    assert [s["id"] for s in timeline["overdue"]["samples"]] == [s4.id, s3.id, s2.id]
    assert timeline["no_due_date"]["count"] == 4
    assert [s["id"] for s in timeline["no_due_date"]["samples"]] == [n2.id, n1.id, n3.id]


def test_eo_fn_16__unpaid_pipeline_buckets_and_filters_ignored(db, M, w1, order_factory, u1, a1, invoice_factory, f2, w2, u4):
    """EO-FN-16 -- unpaid_pipeline buckets by unpaid/partial/overdue; paid,
    voided-invoice, completed-order and voided-order invoices are excluded.
    Rules: R10, R11 (happy)."""
    def mk(payment_status, invoice_status, amount, paid, **order_over):
        o = order_factory(w1, u1, account_id=a1.id, subtotal=amount, total_amount=amount, **order_over)
        inv = invoice_factory(
            w1, a1, invoice_status=invoice_status, payment_status=payment_status,
            invoice_amount=amount, paid_amount=paid, order_id=o.id,
        )
        o.invoice_id = inv.id
        db.flush()
        return o, inv

    v1, _ = mk("unpaid", "confirmed", Decimal("1000"), Decimal("0"))
    v2, _ = mk("partial", "confirmed", Decimal("800"), Decimal("300"))
    v3, _ = mk("overdue", "confirmed", Decimal("600"), Decimal("0"))
    mk("paid", "confirmed", Decimal("100"), Decimal("100"))
    mk("unpaid", "voided", Decimal("50"), Decimal("0"))
    mk("unpaid", "confirmed", Decimal("70"), Decimal("0"), completed_at=T0)
    mk("unpaid", "confirmed", Decimal("90"), Decimal("0"), voided=True)
    order_factory(w1, u1, account_id=a1.id)
    v9, _ = mk("unpaid", "confirmed", Decimal("0"), Decimal("0"))

    result = fn(db, M, w1.id, expense_category="department")
    pipeline = result["unpaid_pipeline"]
    assert [b["key"] for b in pipeline] == ["unpaid", "partial", "overdue"]
    assert [b["label"] for b in pipeline] == ["Unpaid", "Partial", "Overdue"]
    unpaid, partial, overdue = pipeline
    assert unpaid["count"] == 2
    assert unpaid["outstanding_value"] == Decimal("1000.00")
    assert partial["count"] == 1
    assert partial["outstanding_value"] == Decimal("500.00")
    assert overdue["count"] == 1
    assert overdue["outstanding_value"] == Decimal("600.00")
    assert v1.id and v2.id and v3.id and v9.id


def test_eo_fn_17__unpaid_pipeline_samples(db, M, w1, order_factory, u1, a1, invoice_factory):
    """EO-FN-17 -- unpaid_pipeline samples, ordered by outstanding value desc
    across the whole query before grouping.
    Rules: R12 (side-effect)."""
    def mk(payment_status, amount, paid, invoice_status="confirmed", **order_over):
        o = order_factory(w1, u1, account_id=a1.id, subtotal=amount, total_amount=amount, **order_over)
        inv = invoice_factory(
            w1, a1, invoice_status=invoice_status, payment_status=payment_status,
            invoice_amount=amount, paid_amount=paid, order_id=o.id,
        )
        o.invoice_id = inv.id
        db.flush()
        return o

    # "as FN-16": V1-V3, V9 count; V4 (paid), V5 (voided invoice), V6
    # (completed order), V7 (voided order) and V8 (no invoice) must be
    # excluded from the samples -- verifier finding #12.
    v1 = mk("unpaid", Decimal("1000"), Decimal("0"))
    v2 = mk("partial", Decimal("800"), Decimal("300"))
    v3 = mk("overdue", Decimal("600"), Decimal("0"))
    mk("paid", Decimal("100"), Decimal("100"))
    mk("unpaid", Decimal("50"), Decimal("0"), invoice_status="voided")
    mk("unpaid", Decimal("70"), Decimal("0"), completed_at=T0)
    mk("unpaid", Decimal("90"), Decimal("0"), voided=True)
    order_factory(w1, u1, account_id=a1.id)
    v9 = mk("unpaid", Decimal("0"), Decimal("0"))

    result = fn(db, M, w1.id)
    pipeline = {b["key"]: b for b in result["unpaid_pipeline"]}
    assert pipeline["unpaid"]["samples"] == [
        {"id": v1.id, "order_number": v1.expense_number, "total_value": Decimal("1000.00"), "sublabel": "unpaid"},
        {"id": v9.id, "order_number": v9.expense_number, "total_value": Decimal("0"), "sublabel": "unpaid"},
    ]
    assert pipeline["partial"]["samples"] == [
        {"id": v2.id, "order_number": v2.expense_number, "total_value": Decimal("500.00"), "sublabel": "partial"},
    ]
    assert pipeline["overdue"]["samples"] == [
        {"id": v3.id, "order_number": v3.expense_number, "total_value": Decimal("600.00"), "sublabel": "overdue"},
    ]


def test_eo_fn_18__unpaid_pipeline_top_3_samples(db, M, w1, order_factory, u1, a1, invoice_factory):
    """EO-FN-18 -- unpaid samples are capped at 3, highest outstanding first.
    Rules: R12 (boundary)."""
    for amount in (Decimal("100"), Decimal("300"), Decimal("200"), Decimal("400")):
        o = order_factory(w1, u1, account_id=a1.id, subtotal=amount, total_amount=amount)
        inv = invoice_factory(w1, a1, invoice_status="confirmed", payment_status="unpaid", invoice_amount=amount, paid_amount=Decimal("0"), order_id=o.id)
        o.invoice_id = inv.id
        db.flush()

    result = fn(db, M, w1.id)
    unpaid = next(b for b in result["unpaid_pipeline"] if b["key"] == "unpaid")
    assert unpaid["count"] == 4
    assert unpaid["outstanding_value"] == Decimal("1000.00")
    assert [s["total_value"] for s in unpaid["samples"]] == [Decimal("400.00"), Decimal("300.00"), Decimal("200.00")]


@pytest.mark.xfail(strict=True, reason=BUG_748 + " -- fails today on: tie order differs")
def test_eo_fn_19__bug_748_unpaid_sample_tie_order(db, M, w1, order_factory, u1, a1, invoice_factory):
    """EO-FN-19 -- ties in outstanding value have no guaranteed sample order;
    the UI would want order-creation order.
    Rules: R12 [BUG-748]."""
    orders = [order_factory(w1, u1, account_id=a1.id, subtotal=Decimal("100"), total_amount=Decimal("100")) for _ in range(4)]
    for o in reversed(orders):
        inv = invoice_factory(w1, a1, invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal("100"), paid_amount=Decimal("0"), order_id=o.id)
        o.invoice_id = inv.id
        db.flush()

    result = fn(db, M, w1.id)
    unpaid = next(b for b in result["unpaid_pipeline"] if b["key"] == "unpaid")
    assert [s["id"] for s in unpaid["samples"]] == [orders[0].id, orders[1].id, orders[2].id]


def test_eo_fn_20__empty_workspace_all_zero(db, M, w1):
    """EO-FN-20 -- no orders at all -> every bucket present at zero.
    Rules: R13 (boundary)."""
    with patched_now(NOW):
        result = fn(db, M, w1.id)
    for bucket in result["due_timeline"]:
        assert bucket["count"] == 0
        assert bucket["total_value"] == Decimal(0)
        assert bucket["samples"] == []
    for bucket in result["unpaid_pipeline"]:
        assert bucket["count"] == 0
        assert bucket["outstanding_value"] == Decimal(0)
        assert bucket["samples"] == []
    assert result["category_breakdown"] == []
    assert result["open_by_account"] == []


def test_eo_fn_21__unknown_kwarg_raises_typeerror(db, M, w1, H):
    """EO-FN-21 -- an unrecognized filter kwarg raises TypeError.
    Rules: Errors."""
    with pytest.raises(TypeError):
        fn(db, M, w1.id, foo=1)


def test_eo_fn_22__due_timeline_isolation(db, M, w1, w2, order_factory, u4, f2):
    """EO-FN-22 -- the due_timeline only considers the given workspace's orders.
    Rules: R7 (isolation)."""
    with patched_now(NOW):
        order_factory(w2, u4, cost_center_id=f2.id, due_date=date(2026, 3, 10))
        result = fn(db, M, w1.id)
    overdue = next(b for b in result["due_timeline"] if b["key"] == "overdue")
    assert overdue["count"] == 0


def test_eo_fn_23__due_timeline_week_crosses_month_end(db, M, w1, order_factory, u1):
    """EO-FN-23 -- when the coming week crosses into next month, 'this week'
    can include dates past month-end, leaving 'later this month' empty.
    Rules: R8, R9 (boundary)."""
    now = datetime(2026, 3, 30, 10, 0, 0)  # Monday
    with patched_now(now):
        order_factory(w1, u1, due_date=date(2026, 3, 29), subtotal=Decimal("10"), total_amount=Decimal("10"))
        m2 = order_factory(w1, u1, due_date=date(2026, 3, 30), subtotal=Decimal("20"), total_amount=Decimal("20"))
        m3 = order_factory(w1, u1, due_date=date(2026, 3, 31), subtotal=Decimal("30"), total_amount=Decimal("30"))
        m4 = order_factory(w1, u1, due_date=date(2026, 4, 2), subtotal=Decimal("40"), total_amount=Decimal("40"))
        order_factory(w1, u1, due_date=date(2026, 4, 5), subtotal=Decimal("50"), total_amount=Decimal("50"))
        order_factory(w1, u1, due_date=date(2026, 4, 6), subtotal=Decimal("60"), total_amount=Decimal("60"))
        result = fn(db, M, w1.id)
    timeline = {b["key"]: b for b in result["due_timeline"]}
    assert timeline["overdue"]["count"] == 1
    assert timeline["overdue"]["total_value"] == Decimal("10.00")
    assert timeline["due_this_week"]["count"] == 4
    assert timeline["due_this_week"]["total_value"] == Decimal("140.00")
    assert [s["id"] for s in timeline["due_this_week"]["samples"]] == [m2.id, m3.id, m4.id]
    assert timeline["due_later_this_month"]["count"] == 0
    assert timeline["due_later_this_month"]["total_value"] == Decimal(0)
    assert timeline["due_later_this_month"]["samples"] == []
    assert timeline["no_due_date"]["count"] == 0


# --------------------------------------------------------------------------- #
# `delete_expense_order`
# --------------------------------------------------------------------------- #

def test_eo_d_01__happy_delete_cascades(db, M, w1, O, line_factory, approver_factory, event_factory, u1, u2):
    """EO-D-01 -- deleting an order removes its lines/approvers/events and
    leaves other orders untouched.
    Rules: delete_expense_order R4, R5 (happy)."""
    o = O()
    line_factory(o, 1)
    line_factory(o, 2)
    approver_factory(o, u1, assigned_by=u1)
    approver_factory(o, u2, assigned_by=u1)
    event_factory(o, "note", "a")
    event_factory(o, "note", "b")
    event_factory(o, "note", "c")
    p = O()
    p_line = line_factory(p, 1)
    p_approver = approver_factory(p, u1, assigned_by=u1)
    p_event = event_factory(p, "note", "d")

    result = M.delete_expense_order(db, o.id, w1.id)
    assert result is None
    db.expire_all()
    assert db.get(ExpenseOrder, o.id) is None
    assert lines_of(db, o.id) == []
    assert approvers_of(db, o.id) == []
    assert events_of(db, o.id) == []

    assert db.get(ExpenseOrder, p.id) is not None
    assert reread_item(db, p_line.id) is not None
    assert reread_approver(db, p_approver.id) is not None
    assert reread_event(db, p_event.id) is not None
    assert events_of(db, p.id) == [p_event]


def test_eo_d_02__missing_order_404(db, M, w1, O, line_factory):
    """EO-D-02 -- a missing order id -> 404, nothing written.
    Rules: R1 (error)."""
    o = O()
    line_factory(o, 1)
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)
    assert db.get(ExpenseOrder, o.id) is not None
    assert len(lines_of(db, o.id)) == 1


def test_eo_d_03__other_workspace_404(db, M, w1, O5, line_factory):
    """EO-D-03 -- an order of another workspace -> 404, nothing written.
    Rules: R1 (isolation)."""
    line_factory(O5, 1)
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, O5.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert db.get(ExpenseOrder, O5.id) is not None
    assert len(lines_of(db, O5.id)) == 1


def test_eo_d_04__completed_rejected(db, M, w1, O, line_factory, approver_factory, event_factory):
    """EO-D-04 -- a completed order (no invoice) -> 400, nothing written.
    Rules: R2 (error)."""
    o = O(completed_at=T0)
    line_factory(o, 1)
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, o.id, w1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot delete a completed expense order"
    assert db.get(ExpenseOrder, o.id) is not None
    assert len(lines_of(db, o.id)) == 1


def test_eo_d_05__voided_deletes(db, M, w1, O, line_factory):
    """EO-D-05 -- a voided order (no invoice) can still be deleted.
    Rules: R4 (soft-delete)."""
    o = O(voided=True)
    line_factory(o, 1)
    result = M.delete_expense_order(db, o.id, w1.id)
    assert result is None
    db.expire_all()
    assert db.get(ExpenseOrder, o.id) is None
    assert lines_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_742 + " -- fails today on: no captured FOR UPDATE")
def test_eo_d_06__bug_742_locks_order_row(db, M, w1, O, engine):
    """EO-D-06 -- the order row is read FOR UPDATE before deleting.
    Rules: R3 [BUG-742]."""
    o = O()
    with SQLCapture(engine) as cap:
        result = M.delete_expense_order(db, o.id, w1.id)
    assert result is None
    assert cap.locked


@pytest.mark.xfail(strict=True, reason=BUG_742 + " -- fails today on: no exception, order deleted")
def test_eo_d_07__bug_742_draft_invoice_blocks_delete(db, M, w1, O, line_factory, a1, invoice_factory):
    """EO-D-07 -- an order with a linked draft invoice must be voided instead
    of deleted.
    Rules: R4 [BUG-742]."""
    o = O(account_id=a1.id)
    line_factory(o, 1)
    inv = invoice_factory(w1, a1, invoice_status="draft", order_id=o.id)
    o.invoice_id = inv.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, o.id, w1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Void the expense order instead"
    assert db.get(ExpenseOrder, o.id) is not None
    assert db.get(AccountInvoice, inv.id) is not None


@pytest.mark.xfail(strict=True, reason=BUG_742 + " -- fails today on: no exception, order deleted")
def test_eo_d_08__bug_742_confirmed_invoice_blocks_delete(db, M, w1, O, a1, invoice_factory):
    """EO-D-08 -- an order with a linked confirmed invoice must be voided
    instead of deleted.
    Rules: R4 [BUG-742]."""
    o = O(account_id=a1.id)
    inv = invoice_factory(w1, a1, invoice_status="confirmed", order_id=o.id)
    o.invoice_id = inv.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, o.id, w1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Void the expense order instead"
    assert db.get(ExpenseOrder, o.id) is not None


def test_eo_d_09__completed_with_invoice_completed_error_wins(db, M, w1, O, line_factory, approver_factory, event_factory, u1, a1, invoice_factory):
    """EO-D-09 -- a completed order with a confirmed invoice fails on the
    completed check, before the invoice check is ever reached.
    Rules: R2, R4 (boundary)."""
    o = O(account_id=a1.id, completed_at=T0)
    line_factory(o, 1)
    approver_factory(o, u1, assigned_by=u1)
    event_factory(o, "note", "x")
    inv = invoice_factory(w1, a1, invoice_status="confirmed", order_id=o.id)
    o.invoice_id = inv.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, o.id, w1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot delete a completed expense order"
    assert db.get(ExpenseOrder, o.id) is not None
    assert len(lines_of(db, o.id)) == 1
    assert len(approvers_of(db, o.id)) == 1
    assert len(events_of(db, o.id)) == 1
    assert db.get(AccountInvoice, inv.id) is not None


# BUG-1193 (spec R5a, R5b, R5c), cases revision 6. The new `user_id` is passed as
# a keyword. EO-D-01...D-09 above are unchanged and need it too once it exists.

def audit_rows(db, order_id):
    """Convention AUDIT(X): this order's workspace_audit_logs rows, re-read."""
    db.expire_all()
    return list(db.scalars(
        select(WorkspaceAuditLog)
        .where(WorkspaceAuditLog.resource_type == "expense_order", WorkspaceAuditLog.resource_id == order_id)
        .order_by(WorkspaceAuditLog.id)
    ))


def audit_count(db, ws_id=None):
    """Rows of workspace_audit_logs: all of them, or those of one workspace."""
    db.expire_all()
    stmt = select(func.count()).select_from(WorkspaceAuditLog)
    if ws_id is not None:
        stmt = stmt.where(WorkspaceAuditLog.workspace_id == ws_id)
    return db.scalar(stmt)


def order_exists(db, order_id):
    db.expire_all()
    return db.get(ExpenseOrder, order_id) is not None


NO_USER_ID_YET = " -- fails today on: the call raises TypeError (no user_id parameter)"


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_10__bug_1193_delete_leaves_one_audit_row(db, M, w1, O, line_factory, approver_factory, event_factory, u1, u2, u3):
    """EO-D-10 -- deleting an approved order writes the one audit row, with the
    deleter as user_id, and its events are not copied.
    Rules: R5a, R5 [BUG-1193]."""
    o = O(expense_number="EXP-2026-041", subtotal=Decimal("1234.50"), total_amount=Decimal("1234.50"))
    order_id = o.id
    line_factory(o, 1, unit_price=Decimal("1000.00"), line_subtotal=Decimal("1000.00"))
    line_factory(o, 2, unit_price=Decimal("234.50"), line_subtotal=Decimal("234.50"))
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=True, approved_at=T0)
    event_factory(o, "note", "a")
    event_factory(o, "note", "b")
    event_factory(o, "note", "c")

    result = M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert not order_exists(db, order_id)
    assert lines_of(db, order_id) == []
    assert approvers_of(db, order_id) == []
    assert events_of(db, order_id) == []
    # Then 3
    rows = audit_rows(db, order_id)
    assert len(rows) == 1
    # Then 4
    row = rows[0]
    assert row.workspace_id == w1.id
    assert row.user_id == u2.id
    assert row.action == "expense_order_deleted"
    assert row.resource_type == "expense_order"
    assert row.resource_id == order_id
    # Then 5
    assert row.metadata_json == {
        "number": "EXP-2026-041",
        "total_amount": "1234.50",
        "created_by": u1.id,
        "created_at": "2026-01-01T09:00:00",
    }


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_11__bug_1193_zero_total_keeps_two_decimals(db, M, w1, O, u2):
    """EO-D-11 -- a total of 0 is recorded as "0.00".
    Rules: R5a [BUG-1193]."""
    order_id = O().id

    result = M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    rows = audit_rows(db, order_id)
    assert len(rows) == 1
    # Then 3
    assert rows[0].metadata_json["total_amount"] == "0.00"


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_12__bug_1193_voided_order_leaves_a_row_too(db, M, w1, O, line_factory, u2):
    """EO-D-12 -- deleting a voided order leaves the audit row as well.
    Rules: R5a [BUG-1193]."""
    o = O(
        voided=True, expense_number="EXP-2026-042",
        subtotal=Decimal("300.00"), total_amount=Decimal("300.00"),
    )
    order_id = o.id
    line_factory(o, 1, unit_price=Decimal("300.00"), line_subtotal=Decimal("300.00"))

    result = M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert not order_exists(db, order_id)
    # Then 3
    rows = audit_rows(db, order_id)
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == u2.id
    assert rows[0].metadata_json["number"] == "EXP-2026-042"
    assert rows[0].metadata_json["total_amount"] == "300.00"


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_13__bug_1193_only_this_orders_row_is_added(db, M, w1, w2, O, O5, u2):
    """EO-D-13 -- one row is added in the order's workspace and nowhere else.
    Rules: R5a [BUG-1193]."""
    order_id = O().id
    other_id = O().id
    for ws in (w1, w2):
        db.add(WorkspaceAuditLog(workspace_id=ws.id, action="member_added", resource_type="member", resource_id=7))
    db.flush()

    result = M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert audit_count(db, w1.id) == 2
    # Then 3
    assert audit_count(db, w2.id) == 1
    # Then 4
    rows = audit_rows(db, order_id)
    assert len(rows) == 1
    assert rows[0].workspace_id == w1.id
    # Then 5
    assert audit_rows(db, other_id) == []
    assert audit_rows(db, O5.id) == []
    # Then 6
    assert order_exists(db, other_id)
    assert order_exists(db, O5.id)


# Author: claude (a savepoint and a commit spy)
@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_14__bug_1193_row_shares_the_delete_transaction(db, M, w1, O, u2, monkeypatch):
    """EO-D-14 -- the row is flushed with the delete, not committed, and a
    rollback takes both back.
    Rules: R5a [BUG-1193]."""
    order_id = O().id
    sp = db.begin_nested()
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)

    result = M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert len(audit_rows(db, order_id)) == 1
    # Then 3
    assert not order_exists(db, order_id)
    # Then 4
    spy.assert_not_called()
    sp.rollback()
    # Then 5
    assert order_exists(db, order_id)
    # Then 6
    assert audit_rows(db, order_id) == []


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_15__bug_1193_missing_order_writes_no_row(db, M, w1, O, line_factory, u2):
    """EO-D-15 -- a delete refused with 404 writes no audit row.
    Rules: R1, R5b [BUG-1193]."""
    o = O()
    line_factory(o, 1)
    missing = missing_id(db, ExpenseOrder)
    before = audit_count(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, missing, w1.id, user_id=u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)
    # Then 2
    assert audit_count(db) == before
    # Then 3
    assert order_exists(db, o.id)
    assert len(lines_of(db, o.id)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_16__bug_1193_other_workspace_writes_no_row(db, M, w1, O5, line_factory, u2):
    """EO-D-16 -- a delete of another workspace's order writes no audit row.
    Rules: R1, R5b [BUG-1193]."""
    line_factory(O5, 1)
    before = audit_count(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, O5.id, w1.id, user_id=u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    # Then 2
    assert audit_count(db) == before
    # Then 3
    assert order_exists(db, O5.id)
    assert len(lines_of(db, O5.id)) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1193 + NO_USER_ID_YET)
def test_eo_d_17__bug_1193_refused_delete_writes_nothing(db, M, w1, O, line_factory, approver_factory, event_factory, u1, u2):
    """EO-D-17 -- a completed order is refused and nothing at all is written.
    Rules: R2, R5b [BUG-1193]."""
    o = O(completed_at=T0)
    order_id = o.id
    line_factory(o, 1)
    approver_factory(o, u1, assigned_by=u1)
    event_factory(o, "note", "x")
    before = audit_count(db)
    order_before = order_snap(db, order_id)
    la_before = lines_approvers_snap(db, order_id)
    events_before = [e.id for e in events_of(db, order_id)]

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, order_id, w1.id, user_id=u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot delete a completed expense order"
    # Then 2
    assert audit_count(db) == before
    # Then 3
    assert audit_rows(db, order_id) == []
    # Then 4
    assert order_snap(db, order_id) == order_before
    assert lines_approvers_snap(db, order_id) == la_before
    assert [e.id for e in events_of(db, order_id)] == events_before


@pytest.mark.xfail(strict=True, reason=BUG_742 + "; " + BUG_1193 + NO_USER_ID_YET)
def test_eo_d_18__bug_1193_linked_invoice_refusal_writes_no_row(db, M, w1, O, line_factory, a1, invoice_factory, u2):
    """EO-D-18 -- the linked-invoice refusal writes no audit row.
    Rules: R4, R5b [BUG-742, BUG-1193]."""
    o = O(account_id=a1.id)
    line_factory(o, 1)
    inv = invoice_factory(w1, a1, invoice_status="draft", order_id=o.id)
    o.invoice_id = inv.id
    db.flush()
    before = audit_count(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_expense_order(db, o.id, w1.id, user_id=u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Void the expense order instead"
    # Then 2
    assert audit_count(db) == before
    # Then 3
    assert order_exists(db, o.id)
    assert db.get(AccountInvoice, inv.id) is not None


@pytest.mark.xfail(strict=True, reason=BUG_1193 + " -- fails today on: no error, the order is deleted")
def test_eo_d_19__bug_1193_user_id_is_required(db, M, w1, O):
    """EO-D-19 -- a call without user_id raises and deletes nothing.
    Rules: R5c [BUG-1193]."""
    order_id = O().id

    # Then 1
    with pytest.raises(TypeError):
        M.delete_expense_order(db, order_id, w1.id)
    # Then 2
    assert order_exists(db, order_id)
    # Then 3
    assert audit_rows(db, order_id) == []


# --------------------------------------------------------------------------- #
# `add_item`
# --------------------------------------------------------------------------- #
# Default Given: order O with lines 1 ("Line 1", 100.00) and 3 ("Line 3", 50.00)
# (line 2 was removed earlier), totals 150.00. add(d) = add_item(db, o.id,
# ExpenseOrderItemCreate(**d), w1.id, u2.id).

@pytest.fixture
def O_ai(O, line_factory):
    o = O(subtotal=Decimal("150.00"), total_amount=Decimal("150.00"))
    line_factory(o, 1, description="Line 1", unit_price=Decimal("100.00"), line_subtotal=Decimal("100.00"))
    line_factory(o, 3, description="Line 3", unit_price=Decimal("50.00"), line_subtotal=Decimal("50.00"))
    return o


def add_item(db, M, o, w1, u2, **d):
    return M.add_item(db, o.id, ExpenseOrderItemCreate(**d), w1.id, u2.id)


def test_eo_ai_01__happy_adds_line_recalcs_totals_logs_event(db, M, w1, O_ai, u2):
    """EO-AI-01 -- a new line gets the next line_number, totals recalc, event
    logged.
    Rules: add_item R3, R4, R5, R6 (happy)."""
    o = O_ai
    line = add_item(db, M, o, w1, u2, description="Electricity", quantity=2, unit="month", unit_price=Decimal("1500.50"), notes="Q1")
    assert line.id is not None
    r = reread_item(db, line.id)
    assert r.line_number == 4
    assert r.description == "Electricity"
    assert r.quantity == Decimal("2")
    assert r.unit == "month"
    assert r.unit_price == Decimal("1500.50")
    assert r.notes == "Q1"
    assert r.line_subtotal == Decimal("3001.00")
    assert r.workspace_id == w1.id
    assert r.expense_order_id == o.id
    lines = lines_of(db, o.id)
    assert [i.line_number for i in lines] == [1, 3, 4]
    assert lines[0].description == "Line 1" and lines[1].description == "Line 3"
    ro = reread_order(db, o.id)
    assert ro.subtotal == Decimal("3151.00") and ro.total_amount == Decimal("3151.00")
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [("item_added", "Line 4 added")]
    assert events[0].performed_by == u2.id
    assert events[0].metadata_json == {"line_number": 4}


def test_eo_ai_02__first_line_number_1(db, M, w1, O, u2):
    """EO-AI-02 -- the first line on an empty order gets line_number 1.
    Rules: R3 (boundary)."""
    o = O()
    line = add_item(db, M, o, w1, u2, description="Fee", quantity=1, unit_price=10)
    assert line.line_number == 1
    r = reread_order(db, o.id)
    assert r.subtotal == Decimal("10.00") and r.total_amount == Decimal("10.00")


def test_eo_ai_03__quantity_defaults_to_1(db, M, w1, O_ai, u2):
    """EO-AI-03 -- quantity defaults to 1 when omitted. Re-read from the DB
    rather than asserting on the in-memory returned object (verifier finding #8).
    Rules: R4, PID R2 (boundary)."""
    line = add_item(db, M, O_ai, w1, u2, description="Fee", unit_price=25)
    r = reread_item(db, line.id)
    assert r.quantity == Decimal("1")
    assert r.line_subtotal == Decimal("25.00")


def test_eo_ai_04__no_price_zero_subtotal(db, M, w1, O_ai, u2):
    """EO-AI-04 -- no price given -> zero subtotal, totals unchanged.
    Rules: R4, PID R3 (boundary)."""
    add_item(db, M, O_ai, w1, u2, description="Free", quantity=3)
    r = reread_order(db, O_ai.id)
    assert r.subtotal == Decimal("150.00") and r.total_amount == Decimal("150.00")


def test_eo_ai_05__missing_order_404(db, M, w1, O_ai, u2):
    """EO-AI-05 -- a missing order id -> 404, nothing written.
    Rules: R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, missing, ExpenseOrderItemCreate(description="x", quantity=1, unit_price=1), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)
    assert len(lines_of(db, O_ai.id)) == 2
    r = reread_order(db, O_ai.id)
    assert r.subtotal == Decimal("150.00")
    assert events_of(db, O_ai.id) == []


def test_eo_ai_06__other_workspace_404(db, M, w1, O5, u2):
    """EO-AI-06 -- an order of another workspace -> 404, no line added.
    Rules: R1 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, O5.id, ExpenseOrderItemCreate(description="x", quantity=1, unit_price=1), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert lines_of(db, O5.id) == []


def test_eo_ai_07__completed_rejected(db, M, w1, O_ai, u2):
    """EO-AI-07 -- a completed order rejects adding items.
    Rules: R2 (error)."""
    o = O_ai
    mutate(db, o, completed_at=T0)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        add_item(db, M, o, w1, u2, description="X", quantity=1, unit_price=1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"
    assert len(lines_of(db, o.id)) == 2
    assert reread_order(db, o.id).subtotal == Decimal("150.00")
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_754 + " -- fails today on: line added")
def test_eo_ai_08__bug_754_voided_rejected(db, M, w1, O_ai, u2):
    """EO-AI-08 -- a voided order should reject adding items.
    Rules: R2 [BUG-754]."""
    o = O_ai
    mutate(db, o, voided=True)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        add_item(db, M, o, w1, u2, description="X", quantity=1, unit_price=1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert len(lines_of(db, o.id)) == 2


@pytest.mark.xfail(strict=True, reason=BUG_743 + " -- fails today on: no captured FOR UPDATE")
def test_eo_ai_09__bug_743_locks_order_row(db, M, w1, O_ai, u2, engine):
    """EO-AI-09 -- the parent order row is read FOR UPDATE before adding.
    Rules: R2 [BUG-743]."""
    with SQLCapture(engine) as cap:
        line = add_item(db, M, O_ai, w1, u2, description="X", quantity=1, unit_price=1)
    assert line.id is not None
    assert cap.locked


def test_eo_ai_10__resets_approvals_when_recorded(db, M, w1, O_ai, u1, u2, u3, approver_factory):
    """EO-AI-10 -- adding a line resets recorded approvals.
    Rules: R7 (side-effect)."""
    o = O_ai
    approver_factory(o, u3, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u1, assigned_by=u1, approved=False)
    add_item(db, M, o, w1, u2, description="X", quantity=1, unit_price=1)
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    events = events_of(db, o.id)
    assert [(e.event_type, e.description) for e in events] == [
        ("item_added", "Line 4 added"),
        ("approvals_reset", "Expense items edited (1 approval(s) cleared)"),
    ]
    assert events[1].performed_by == u2.id


def test_eo_ai_11__no_reset_when_no_recorded_approvals(db, M, w1, O_ai, u1, u3, u2, approver_factory):
    """EO-AI-11 -- adding a line does not reset approvals when none are
    recorded.
    Rules: R7 (boundary)."""
    o = O_ai
    approver_factory(o, u3, assigned_by=u1, approved=False)
    add_item(db, M, o, w1, u2, description="X", quantity=1, unit_price=1)
    events = events_of(db, o.id)
    assert [e.event_type for e in events if e.event_type == "approvals_reset"] == []
    u3_row = approver_row(db, o.id, u3.id)
    assert u3_row.approved is False


# --------------------------------------------------------------------------- #
# `update_item`
# --------------------------------------------------------------------------- #
# Default Given: order O with line L1 (line 1, "Paper", qty 2, unit "box",
# price 10.00, subtotal 20.00, notes "n") and line L2 (line 2, qty 1, price
# 5.00, subtotal 5.00); totals 25.00. upd(d) = update_item(db, L1.id,
# ExpenseOrderItemUpdate(**d), w1.id, u2.id).

@pytest.fixture
def O_ui(O, line_factory):
    o = O(subtotal=Decimal("25.00"), total_amount=Decimal("25.00"))
    l1 = line_factory(o, 1, description="Paper", quantity=Decimal("2"), unit="box", unit_price=Decimal("10.00"), line_subtotal=Decimal("20.00"), notes="n")
    l2 = line_factory(o, 2, quantity=Decimal("1"), unit_price=Decimal("5.00"), line_subtotal=Decimal("5.00"))
    return SimpleNamespace(o=o, l1=l1, l2=l2)


def upd(db, M, l1, w1, u2, **d):
    return M.update_item(db, l1.id, ExpenseOrderItemUpdate(**d), w1.id, u2.id)


def test_eo_ui_01__happy_updates_line_recalcs_totals_logs_event(db, M, w1, O_ui, u2):
    """EO-UI-01 -- updating quantity recalculates the line and order totals,
    logs an event.
    Rules: update_item R5, R6, R7, R8 (happy)."""
    g = O_ui
    result = upd(db, M, g.l1, w1, u2, quantity=3)
    assert result.id == g.l1.id
    r = reread_item(db, g.l1.id)
    assert r.quantity == Decimal("3")
    assert r.unit_price == Decimal("10.00")
    assert r.line_subtotal == Decimal("30.00")
    assert r.description == "Paper" and r.unit == "box" and r.notes == "n"
    ro = reread_order(db, g.o.id)
    assert ro.subtotal == Decimal("35.00") and ro.total_amount == Decimal("35.00")
    events = events_of(db, g.o.id)
    assert [(e.event_type, e.description) for e in events] == [("item_updated", "Line 1 updated")]
    assert events[0].performed_by == u2.id
    assert events[0].metadata_json is None


def test_eo_ui_02__price_change_keeps_stored_quantity(db, M, w1, O_ui, u2):
    """EO-UI-02 -- a price-only change uses the currently stored quantity.
    Rules: R6 (boundary)."""
    g = O_ui
    upd(db, M, g.l1, w1, u2, unit_price=Decimal("12.50"))
    assert reread_item(db, g.l1.id).line_subtotal == Decimal("25.00")
    assert reread_order(db, g.o.id).total_amount == Decimal("30.00")


def test_eo_ui_03__non_amount_fields_do_not_touch_subtotal(db, M, w1, O_ui, u2):
    """EO-UI-03 -- changing description/unit/notes leaves the subtotal as is.
    Rules: R6 (boundary)."""
    g = O_ui
    upd(db, M, g.l1, w1, u2, description="Paper A4", unit="ream", notes="m")
    r = reread_item(db, g.l1.id)
    assert r.description == "Paper A4" and r.unit == "ream" and r.notes == "m"
    assert r.line_subtotal == Decimal("20.00")
    assert reread_order(db, g.o.id).total_amount == Decimal("25.00")
    assert len([e for e in events_of(db, g.o.id) if e.event_type == "item_updated"]) == 1


def test_eo_ui_04__no_price_quantity_change_keeps_zero_subtotal(db, M, w1, O, line_factory, u2):
    """EO-UI-04 -- when unit_price is None, changing quantity keeps the
    subtotal at zero.
    Rules: R6 (boundary)."""
    o = O(subtotal=Decimal("5.00"), total_amount=Decimal("5.00"))
    l1 = line_factory(o, 1, unit_price=None, line_subtotal=Decimal("0"))
    line_factory(o, 2, unit_price=Decimal("5.00"), line_subtotal=Decimal("5.00"))
    upd(db, M, l1, w1, u2, quantity=4)
    assert reread_item(db, l1.id).line_subtotal == Decimal("0")
    assert reread_order(db, o.id).total_amount == Decimal("5.00")


def test_eo_ui_05__missing_item_404(db, M, w1, O_ui, u2):
    """EO-UI-05 -- a missing item id -> 404, nothing written (L1, L2, totals
    25.00, 0 events -- verifier finding #6: the previous pass checked only the
    order total and events, not both lines).
    Rules: R1 (error)."""
    g = O_ui
    missing = missing_id(db, ExpenseOrderItem)
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, missing, ExpenseOrderItemUpdate(quantity=9), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    l1 = reread_item(db, g.l1.id)
    assert l1.quantity == Decimal("2") and l1.unit_price == Decimal("10.00") and l1.line_subtotal == Decimal("20.00")
    l2 = reread_item(db, g.l2.id)
    assert l2.quantity == Decimal("1") and l2.unit_price == Decimal("5.00") and l2.line_subtotal == Decimal("5.00")
    assert reread_order(db, g.o.id).total_amount == Decimal("25.00")
    assert events_of(db, g.o.id) == []


def test_eo_ui_06__other_workspace_item_404(db, M, w1, O5, line_factory, u2):
    """EO-UI-06 -- an item of another workspace's order -> 404.
    Rules: R1 (isolation)."""
    l5 = line_factory(O5, 1)
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, l5.id, ExpenseOrderItemUpdate(quantity=9), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    assert reread_item(db, l5.id).quantity == Decimal("1")


def test_eo_ui_07__inconsistent_item_order_mismatch_404(db, M, w1, O5):
    """EO-UI-07 -- an item whose workspace_id is W1 but whose order belongs to
    W2 (inconsistent data) -> 404 from the order lookup.
    Rules: R2 (error)."""
    lx = ExpenseOrderItem(
        workspace_id=w1.id, expense_order_id=O5.id, line_number=1, description="x",
        quantity=Decimal("1"), unit_price=Decimal("1"), line_subtotal=Decimal("1"),
    )
    db.add(lx)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, lx.id, ExpenseOrderItemUpdate(quantity=9), w1.id, 1)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert reread_item(db, lx.id).quantity == Decimal("1")


def test_eo_ui_08__completed_rejected(db, M, w1, O_ui, u2):
    """EO-UI-08 -- a completed order rejects item updates; nothing written
    (L1, L2, 0 events -- verifier finding #6: the previous pass checked only
    L1's quantity).
    Rules: R3 (error)."""
    g = O_ui
    mutate(db, g.o, completed_at=T0)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, g.l1, w1, u2, quantity=3)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"
    assert reread_item(db, g.l1.id).quantity == Decimal("2")
    assert reread_item(db, g.l2.id).quantity == Decimal("1")
    assert events_of(db, g.o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_754 + " -- fails today on: line changed")
def test_eo_ui_09__bug_754_voided_rejected(db, M, w1, O_ui, u2):
    """EO-UI-09 -- a voided order should reject item updates.
    Rules: R3 [BUG-754]."""
    g = O_ui
    mutate(db, g.o, voided=True)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, g.l1, w1, u2, quantity=3)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert reread_item(db, g.l1.id).quantity == Decimal("2")


@pytest.mark.xfail(strict=True, reason=BUG_743 + " -- fails today on: no captured FOR UPDATE")
def test_eo_ui_10__bug_743_locks_order_row(db, M, w1, O_ui, u2, engine):
    """EO-UI-10 -- the parent order row is read FOR UPDATE before updating.
    Rules: R3 [BUG-743]."""
    g = O_ui
    with SQLCapture(engine) as cap:
        result = upd(db, M, g.l1, w1, u2, quantity=3)
    assert result.id == g.l1.id
    assert cap.locked


def test_eo_ui_11__empty_payload_no_change(db, M, w1, O_ui, u2):
    """EO-UI-11 -- an empty payload changes nothing.
    Rules: R4 (boundary)."""
    g = O_ui
    result = upd(db, M, g.l1, w1, u2)
    assert result.id == g.l1.id
    r = reread_item(db, g.l1.id)
    assert r.description == "Paper" and r.quantity == Decimal("2") and r.unit == "box"
    assert r.unit_price == Decimal("10.00") and r.line_subtotal == Decimal("20.00") and r.notes == "n"
    assert reread_order(db, g.o.id).total_amount == Decimal("25.00")


@pytest.mark.xfail(strict=True, reason=BUG_753 + " -- fails today on: notes still 'n'")
def test_eo_ui_12__bug_753_null_notes_not_cleared(db, M, w1, O_ui, u2):
    """EO-UI-12 -- an explicit null should clear notes.
    Rules: R4 [BUG-753]."""
    g = O_ui
    upd(db, M, g.l1, w1, u2, notes=None)
    assert reread_item(db, g.l1.id).notes is None


@pytest.mark.xfail(strict=True, reason=BUG_753 + " -- fails today on: unit_price still 10.00")
def test_eo_ui_13__bug_753_null_unit_price_not_cleared(db, M, w1, O_ui, u2):
    """EO-UI-13 -- an explicit null should clear unit_price and zero the
    subtotal.
    Rules: R4, R6 [BUG-753]."""
    g = O_ui
    upd(db, M, g.l1, w1, u2, unit_price=None)
    r = reread_item(db, g.l1.id)
    assert r.unit_price is None
    assert r.line_subtotal == Decimal("0")
    assert reread_order(db, g.o.id).total_amount == Decimal("5.00")


@pytest.mark.xfail(strict=True, reason=BUG_753 + " -- fails today on: no ValidationError")
def test_eo_ui_14__bug_753_schema_rejects_null_quantity():
    """EO-UI-14 -- the schema should reject an explicit null quantity.
    Rules: R4 [BUG-753]."""
    with pytest.raises(ValidationError):
        ExpenseOrderItemUpdate(quantity=None)


@pytest.mark.xfail(strict=True, reason=BUG_740 + " -- fails today on: 1 item_updated event")
def test_eo_ui_15__bug_740_empty_payload_still_logs(db, M, w1, O_ui, u2):
    """EO-UI-15 -- an empty payload should not log an item_updated event.
    Rules: R8 [BUG-740]."""
    upd(db, M, O_ui.l1, w1, u2)
    assert events_of(db, O_ui.o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_740 + " -- fails today on: 1 item_updated event")
def test_eo_ui_16__bug_740_unchanged_values_still_log(db, M, w1, O_ui, u2):
    """EO-UI-16 -- sending the stored values unchanged should not log an
    event.
    Rules: R8 [BUG-740]."""
    upd(db, M, O_ui.l1, w1, u2, quantity=2, description="Paper")
    assert events_of(db, O_ui.o.id) == []


def test_eo_ui_17__resets_approvals_when_recorded(db, M, w1, O_ui, u1, u2, u3, approver_factory):
    """EO-UI-17 -- updating a line resets recorded approvals.
    Rules: R9 (side-effect)."""
    g = O_ui
    approver_factory(g.o, u3, assigned_by=u1, approved=True, approved_at=T0)
    upd(db, M, g.l1, w1, u2, quantity=3)
    u3_row = approver_row(db, g.o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    events = events_of(db, g.o.id)
    assert [e.event_type for e in events if e.event_type == "item_updated"] == ["item_updated"]
    reset_events = [e for e in events if e.event_type == "approvals_reset"]
    assert len(reset_events) == 1
    assert reset_events[0].description == "Expense items edited (1 approval(s) cleared)"
    assert reset_events[0].performed_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_740 + " -- fails today on: U3 approval cleared")
def test_eo_ui_18__bug_740_empty_payload_still_resets(db, M, w1, O_ui, u1, u2, u3, approver_factory):
    """EO-UI-18 -- an empty payload should not reset approvals.
    Rules: R9 [BUG-740]."""
    g = O_ui
    approver_factory(g.o, u3, assigned_by=u1, approved=True, approved_at=T0)
    upd(db, M, g.l1, w1, u2)
    u3_row = approver_row(db, g.o.id, u3.id)
    assert u3_row.approved is True and u3_row.approved_at == T0
    assert [e.event_type for e in events_of(db, g.o.id) if e.event_type == "approvals_reset"] == []


def test_eo_ui_19__no_reset_when_no_recorded_approvals(db, M, w1, O_ui, u1, u2, u3, approver_factory):
    """EO-UI-19 -- updating a line does not reset approvals when none are
    recorded.
    Rules: R9 (boundary)."""
    g = O_ui
    approver_factory(g.o, u3, assigned_by=u1, approved=False)
    upd(db, M, g.l1, w1, u2, quantity=3)
    assert [e.event_type for e in events_of(db, g.o.id) if e.event_type == "approvals_reset"] == []


@pytest.mark.xfail(strict=True, reason=BUG_751 + " -- fails today on: field present")
def test_eo_ui_20__bug_751_approved_field_removed():
    """EO-UI-20 -- the 'approved' field should not be client-writable.
    Rules: Inputs [BUG-751]."""
    assert "approved" not in ExpenseOrderItemUpdate.model_fields


def test_eo_ui_21__both_quantity_and_price_change(db, M, w1, O_ui, u2):
    """EO-UI-21 -- changing quantity and price together recomputes the
    subtotal from both new values.
    Rules: R6 (boundary)."""
    g = O_ui
    upd(db, M, g.l1, w1, u2, quantity=3, unit_price=4)
    assert reread_item(db, g.l1.id).line_subtotal == Decimal("12.00")
    assert reread_order(db, g.o.id).total_amount == Decimal("17.00")


# --------------------------------------------------------------------------- #
# `remove_item`
# --------------------------------------------------------------------------- #
# Default Given: order O with lines 1 (10.00), 2 (20.00), 3 (30.00); totals
# 60.00. rm(L) = remove_item(db, L.id, w1.id, u2.id).

@pytest.fixture
def O_ri(O, line_factory):
    o = O(subtotal=Decimal("60.00"), total_amount=Decimal("60.00"))
    l1 = line_factory(o, 1, unit_price=Decimal("10.00"), line_subtotal=Decimal("10.00"))
    l2 = line_factory(o, 2, unit_price=Decimal("20.00"), line_subtotal=Decimal("20.00"))
    l3 = line_factory(o, 3, unit_price=Decimal("30.00"), line_subtotal=Decimal("30.00"))
    return SimpleNamespace(o=o, l1=l1, l2=l2, l3=l3)


def rm(db, M, line, w1, u2):
    return M.remove_item(db, line.id, w1.id, u2.id)


def test_eo_ri_01__happy_removes_line_recalcs_totals_logs_event(db, M, w1, O_ri, u2):
    """EO-RI-01 -- removing a line recalculates totals and logs an event.
    Rules: remove_item R4, R5, R6 (happy)."""
    g = O_ri
    result = rm(db, M, g.l2, w1, u2)
    assert result.line_number == 2
    assert result.expense_order_id == g.o.id
    lines = lines_of(db, g.o.id)
    assert [i.line_number for i in lines] == [1, 3]
    ro = reread_order(db, g.o.id)
    assert ro.subtotal == Decimal("40.00") and ro.total_amount == Decimal("40.00")
    events = events_of(db, g.o.id)
    assert [(e.event_type, e.description) for e in events] == [("item_removed", "Line 2 removed")]
    assert events[0].performed_by == u2.id


def test_eo_ri_02__removing_only_line_zeroes_totals(db, M, w1, O, line_factory, u2):
    """EO-RI-02 -- removing the only line zeroes the order totals.
    Rules: R5 (boundary)."""
    o = O(subtotal=Decimal("10.00"), total_amount=Decimal("10.00"))
    l1 = line_factory(o, 1, unit_price=Decimal("10.00"), line_subtotal=Decimal("10.00"))
    rm(db, M, l1, w1, u2)
    r = reread_order(db, o.id)
    assert r.subtotal == Decimal("0") and r.total_amount == Decimal("0")


def test_eo_ri_03__missing_item_404(db, M, w1, O_ri, u2):
    """EO-RI-03 -- a missing item id -> 404, nothing written.
    Rules: R1 (error)."""
    missing = missing_id(db, ExpenseOrderItem)
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, missing, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    assert len(lines_of(db, O_ri.o.id)) == 3
    assert reread_order(db, O_ri.o.id).total_amount == Decimal("60.00")
    assert events_of(db, O_ri.o.id) == []


def test_eo_ri_04__other_workspace_item_404(db, M, w1, O5, line_factory, u2):
    """EO-RI-04 -- an item of another workspace's order -> 404.
    Rules: R1 (isolation)."""
    l5 = line_factory(O5, 1)
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, l5.id, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    assert reread_item(db, l5.id) is not None


def test_eo_ri_05__inconsistent_item_order_mismatch_404(db, M, w1, O5, u2):
    """EO-RI-05 -- an item whose workspace_id is W1 but whose order belongs to
    W2 -> 404 from the order lookup.
    Rules: R2 (error)."""
    lx = ExpenseOrderItem(
        workspace_id=w1.id, expense_order_id=O5.id, line_number=1, description="x",
        quantity=Decimal("1"), unit_price=Decimal("1"), line_subtotal=Decimal("1"),
    )
    db.add(lx)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, lx.id, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert reread_item(db, lx.id) is not None


def test_eo_ri_06__completed_rejected(db, M, w1, O_ri, u2):
    """EO-RI-06 -- a completed order rejects removing items.
    Rules: R3 (error)."""
    g = O_ri
    mutate(db, g.o, completed_at=T0)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        rm(db, M, g.l2, w1, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"
    assert len(lines_of(db, g.o.id)) == 3
    assert reread_order(db, g.o.id).total_amount == Decimal("60.00")
    assert events_of(db, g.o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_754 + " -- fails today on: line removed")
def test_eo_ri_07__bug_754_voided_rejected(db, M, w1, O_ri, u2):
    """EO-RI-07 -- a voided order should reject removing items.
    Rules: R3 [BUG-754]."""
    g = O_ri
    mutate(db, g.o, voided=True)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        rm(db, M, g.l2, w1, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert len(lines_of(db, g.o.id)) == 3


@pytest.mark.xfail(strict=True, reason=BUG_743 + " -- fails today on: no captured FOR UPDATE")
def test_eo_ri_08__bug_743_locks_order_row(db, M, w1, O_ri, u2, engine):
    """EO-RI-08 -- the parent order row is read FOR UPDATE before removing.
    Rules: R3 [BUG-743]."""
    g = O_ri
    with SQLCapture(engine) as cap:
        rm(db, M, g.l2, w1, u2)
    assert cap.locked


def test_eo_ri_09__resets_approvals_when_recorded(db, M, w1, O_ri, u1, u2, u3, approver_factory):
    """EO-RI-09 -- removing a line resets recorded approvals.
    Rules: R7 (side-effect)."""
    g = O_ri
    approver_factory(g.o, u3, assigned_by=u1, approved=True, approved_at=T0)
    rm(db, M, g.l2, w1, u2)
    u3_row = approver_row(db, g.o.id, u3.id)
    assert u3_row.approved is False and u3_row.approved_at is None
    events = events_of(db, g.o.id)
    assert [(e.event_type, e.description) for e in events] == [
        ("item_removed", "Line 2 removed"),
        ("approvals_reset", "Expense items edited (1 approval(s) cleared)"),
    ]


def test_eo_ri_10__no_reset_when_no_recorded_approvals(db, M, w1, O_ri, u1, u2, u3, approver_factory):
    """EO-RI-10 -- removing a line does not reset approvals when none are
    recorded.
    Rules: R7 (boundary)."""
    g = O_ri
    approver_factory(g.o, u3, assigned_by=u1, approved=False)
    rm(db, M, g.l2, w1, u2)
    assert [e.event_type for e in events_of(db, g.o.id) if e.event_type == "approvals_reset"] == []


# --------------------------------------------------------------------------- #
# `get_items`
# --------------------------------------------------------------------------- #

def test_eo_gi_01__returns_lines_sorted_by_line_number(db, M, w1, O, line_factory):
    """EO-GI-01 -- lines are returned sorted by line_number regardless of
    insertion order.
    Rules: get_items R2 (happy)."""
    o = O()
    line_factory(o, 3)
    line_factory(o, 1)
    line_factory(o, 2)
    result = M.get_items(db, o.id, w1.id)
    assert [i.line_number for i in result] == [1, 2, 3]


def test_eo_gi_02__no_lines_empty_list(db, M, w1, O):
    """EO-GI-02 -- an order with no lines -> [].
    Rules: R2 (boundary)."""
    o = O()
    assert M.get_items(db, o.id, w1.id) == []


def test_eo_gi_03__missing_order_404(db, M, w1):
    """EO-GI-03 -- a missing order id -> 404.
    Rules: R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)


def test_eo_gi_04__other_workspace_404(db, M, w1, O5, line_factory):
    """EO-GI-04 -- an order of another workspace -> 404.
    Rules: R1 (isolation)."""
    line_factory(O5, 1)
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, O5.id, w1.id)
    assert exc.value.status_code == 404


def test_eo_gi_05__only_same_workspace_lines_returned(db, M, w1, w2, O, line_factory):
    """EO-GI-05 -- a line row stored under another workspace is not returned,
    even though it points at this order.
    Rules: R2 (isolation)."""
    o = O()
    line_factory(o, 1)
    line_factory(o, 2, workspace_id=w2.id)
    result = M.get_items(db, o.id, w1.id)
    assert [i.line_number for i in result] == [1]


# --------------------------------------------------------------------------- #
# `_recalc_totals`
# --------------------------------------------------------------------------- #

def test_eo_rt_01__sums_line_subtotals_treating_null_as_zero(db, M, w1, O, line_factory):
    """EO-RT-01 -- totals are the sum of line subtotals, null treated as zero.
    Rules: _recalc_totals R1 (happy)."""
    o = O()
    line_factory(o, 1, line_subtotal=Decimal("10.00"))
    line_factory(o, 2, line_subtotal=Decimal("20.50"))
    line_factory(o, 3, line_subtotal=None)
    M._recalc_totals(db, o)
    r = reread_order(db, o.id)
    assert r.subtotal == Decimal("30.50") and r.total_amount == Decimal("30.50")


def test_eo_rt_02__no_lines_zeroes_totals(db, M, w1, O):
    """EO-RT-02 -- no lines -> totals zeroed.
    Rules: R1 (boundary)."""
    o = O(subtotal=Decimal("99.00"), total_amount=Decimal("99.00"))
    M._recalc_totals(db, o)
    r = reread_order(db, o.id)
    assert r.subtotal == Decimal("0") and r.total_amount == Decimal("0")


def test_eo_rt_03__other_workspace_lines_ignored(db, M, w1, w2, O, line_factory):
    """EO-RT-03 -- a line row stored under another workspace is not counted.
    Rules: R1 (isolation)."""
    o = O(subtotal=Decimal("500.00"), total_amount=Decimal("500.00"))
    line_factory(o, 1, line_subtotal=Decimal("10.00"))
    line_factory(o, 2, workspace_id=w2.id, line_subtotal=Decimal("500.00"))
    M._recalc_totals(db, o)
    r = reread_order(db, o.id)
    assert r.subtotal == Decimal("10.00") and r.total_amount == Decimal("10.00")


# --------------------------------------------------------------------------- #
# `list_approvers`
# --------------------------------------------------------------------------- #

def test_eo_la_01__ordered_by_assigned_at_with_profile_and_position(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-LA-01 -- approvers are returned ordered by assigned_at, each paired with
    the user's profile and workspace position.
    Rules: list_approvers R2, R3, R4 (happy)."""
    o = O()
    approver_factory(o, u3, assigned_by=u1, assigned_at=T0 + timedelta(hours=2))
    approver_factory(o, u2, assigned_by=u1, assigned_at=T0 + timedelta(hours=1))
    approver_factory(o, u1, assigned_by=u1, assigned_at=T0 + timedelta(hours=3))
    result = M.list_approvers(db, o.id, w1.id)
    assert [r[0].user_id for r in result] == [u2.id, u3.id, u1.id]
    u2_row, u2_profile, u2_position = result[0]
    assert u2_row.user_id == u2.id
    assert u2_profile.id == u2.id
    assert u2_position == "Accountant"
    _, _, u3_position = result[1]
    assert u3_position is None


def test_eo_la_02__suspended_member_position_still_shown(db, M, w1, O, u1, approver_factory):
    """EO-LA-02 -- a suspended member's workspace position is still reported.
    Rules: list_approvers R4 (boundary)."""
    suspended = make_profile(db, name="Suspended Guy")
    _member(db, w1, suspended, position="Driver", status="suspended")
    o = O()
    approver_factory(o, suspended, assigned_by=u1)
    result = M.list_approvers(db, o.id, w1.id)
    assert result[0][2] == "Driver"


def test_eo_la_03__member_of_other_workspace_only_no_position(db, M, w1, w2, O, u1, approver_factory):
    """EO-LA-03 -- a user who is only a member of another workspace has no position here.
    Rules: list_approvers R4 (isolation)."""
    outsider = make_profile(db, name="Clerk Guy")
    _member(db, w2, outsider, position="Clerk")
    o = O()
    approver_factory(o, outsider, assigned_by=u1)
    result = M.list_approvers(db, o.id, w1.id)
    assert result[0][1].id == outsider.id
    assert result[0][2] is None


def test_eo_la_05__no_approvers_empty_list(db, M, w1, O):
    """EO-LA-05 -- an order with no approvers returns [].
    Rules: list_approvers R5 (boundary)."""
    o = O()
    assert M.list_approvers(db, o.id, w1.id) == []


def test_eo_la_06__missing_order_404(db, M, w1):
    """EO-LA-06 -- an unknown order id raises 404.
    Rules: list_approvers R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)


def test_eo_la_07__other_workspace_404(db, M, w1, O5):
    """EO-LA-07 -- another workspace's order raises 404.
    Rules: list_approvers R1 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, O5.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)


# --------------------------------------------------------------------------- #
# `approval_summary`
# --------------------------------------------------------------------------- #

def test_eo_as_01__counts_approved_vs_total(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-AS-01 -- approved count and total approvers with no explicit requirement.
    Rules: approval_summary R1, R3, R5 (happy)."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    assert M.approval_summary(db, o) == (2, 3, False)


def test_eo_as_02__all_approved_met(db, M, w1, O, u1, u2, approver_factory):
    """EO-AS-02 -- every approver approved is met.
    Rules: approval_summary R3, R5 (boundary)."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    assert M.approval_summary(db, o) == (2, 2, True)


def test_eo_as_03__explicit_requirement_met(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-AS-03 -- an explicit required_approvals reached is met even with a pending approver.
    Rules: approval_summary R2, R5 (boundary)."""
    o = O(required_approvals=2)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    assert M.approval_summary(db, o) == (2, 2, True)


def test_eo_as_04__explicit_requirement_not_met(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-AS-04 -- an explicit required_approvals not yet reached is not met.
    Rules: approval_summary R2, R5 (boundary)."""
    o = O(required_approvals=2)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=False)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    assert M.approval_summary(db, o) == (1, 2, False)


def test_eo_as_05__explicit_zero_requirement_met_without_approvers(db, M, w1, O):
    """EO-AS-05 -- required_approvals=0 with no approvers is met.
    Rules: approval_summary R2 (boundary)."""
    o = O(required_approvals=0)
    assert M.approval_summary(db, o) == (0, 0, True)


@pytest.mark.xfail(strict=True, reason=BUG_755 + " -- fails today on: returns (0, 0, True)")
def test_eo_as_06__bug_755_no_approvers_no_requirement_not_vacuously_met(db, M, w1, O):
    """EO-AS-06 -- no explicit requirement and no approvers should require 1, not 0.
    Rules: approval_summary R4 [BUG-755]."""
    o = O(required_approvals=None)
    assert M.approval_summary(db, o) == (0, 1, False)


def test_eo_as_07__isolation_other_order_not_counted(db, M, w1, O, u1, approver_factory):
    """EO-AS-07 -- another order's approvers do not affect this order's summary.
    Rules: approval_summary R1 (isolation)."""
    o = O()
    p = O()
    approver_factory(o, u1, assigned_by=u1, approved=False)
    approver_factory(p, u1, assigned_by=u1, approved=True, approved_at=T0)
    assert M.approval_summary(db, o) == (0, 1, False)


# --------------------------------------------------------------------------- #
# `approvals_met`
# --------------------------------------------------------------------------- #

def test_eo_am_01__met_when_all_approved(db, M, w1, O, u1, u2, approver_factory):
    """EO-AM-01 -- approvals_met mirrors approval_summary's met flag (all approved).
    Rules: approvals_met R1 (happy)."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    assert M.approvals_met(db, o) is True


def test_eo_am_02__not_met_with_pending_approver(db, M, w1, O, u1, u2, u3, approver_factory):
    """EO-AM-02 -- approvals_met is False while an approver is still pending.
    Rules: approvals_met R1 (boundary)."""
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    assert M.approvals_met(db, o) is False


@pytest.mark.xfail(strict=True, reason=BUG_755 + " -- fails today on: True")
def test_eo_am_03__bug_755_no_approvers_no_requirement_not_met(db, M, w1, O):
    """EO-AM-03 -- no explicit requirement and no approvers should not be met.
    Rules: approvals_met R1 [BUG-755]."""
    o = O(required_approvals=None)
    assert M.approvals_met(db, o) is False


# --------------------------------------------------------------------------- #
# `add_approver`
# --------------------------------------------------------------------------- #
# "aa(u)" = add_approver(db, o.id, u.id, w1.id, assigned_by=assigned_by.id);
# O_aa = default order with approver U1 approved.

@pytest.fixture
def O_aa(O, u1, approver_factory):
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    return o


def aa(db, M, o, w1, user, assigned_by):
    return M.add_approver(db, o.id, user.id, w1.id, assigned_by=assigned_by.id)


def test_eo_aa_01__happy_adds_approver_logs_event(db, M, w1, O_aa, u1, u3):
    """EO-AA-01 -- adding an approver creates a pending row and logs the event.
    Rules: add_approver R4, R5, R6 (happy)."""
    real_utcnow = real_window()
    before = real_utcnow()
    row = aa(db, M, O_aa, w1, u3, u1)
    after = real_utcnow()
    assert row.user_id == u3.id
    assert row.assigned_by == u1.id
    assert row.approved is False
    assert row.approved_at is None
    assert before <= row.assigned_at <= after
    assert len(approvers_of(db, O_aa.id)) == 2
    u1_row = approver_row(db, O_aa.id, u1.id)
    assert u1_row.approved is True and u1_row.approved_at == T0
    evs = events_of(db, O_aa.id)
    assert events_as_pairs(evs) == [E("approver_added", "Added Rahim Uddin as approver")]
    assert evs[0].performed_by == u1.id
    assert evs[0].metadata_json == {"user_id": u3.id, "user_name": "Rahim Uddin"}


def test_eo_aa_02__missing_order_404(db, M, w1, u1, u3):
    """EO-AA-02 -- an unknown order id raises 404 and writes nothing.
    Rules: add_approver R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, missing, u3.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)
    assert approver_row(db, missing, u3.id) is None
    assert ws_counts(db, w1.id)[3] == 0


def test_eo_aa_03__other_workspace_404(db, M, w1, O5, u1, u3):
    """EO-AA-03 -- another workspace's order raises 404.
    Rules: add_approver R1 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O5, w1, u3, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert approver_row(db, O5.id, u3.id) is None


@pytest.mark.xfail(strict=True, reason=BUG_756 + " -- fails today on: approver added")
def test_eo_aa_04__bug_756_completed_rejected(db, M, w1, O, u1, u3, approver_factory):
    """EO-AA-04 -- a completed order must reject adding an approver.
    Rules: add_approver R1 [BUG-756]."""
    o = O(completed_at=T0)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    with pytest.raises(HTTPException) as exc:
        aa(db, M, o, w1, u3, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"
    assert approver_row(db, o.id, u3.id) is None
    assert events_of(db, o.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_754 + " -- fails today on: approver added")
def test_eo_aa_05__bug_754_voided_rejected(db, M, w1, O, u1, u3, approver_factory):
    """EO-AA-05 -- a voided order must reject adding an approver.
    Rules: add_approver R1 [BUG-754]."""
    o = O(voided=True)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    with pytest.raises(HTTPException) as exc:
        aa(db, M, o, w1, u3, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert approver_row(db, o.id, u3.id) is None
    assert events_of(db, o.id) == []


def test_eo_aa_06__no_membership_rejected(db, M, w1, O_aa, u1, u5):
    """EO-AA-06 -- a user with no membership anywhere cannot be added; nothing
    written (verifier finding #6: previous pass did not check events).
    Rules: add_approver R2 (error)."""
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O_aa, w1, u5, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert approver_row(db, O_aa.id, u5.id) is None
    assert events_of(db, O_aa.id) == []


def test_eo_aa_07__suspended_member_rejected(db, M, w1, O_aa, u1, u3):
    """EO-AA-07 -- a suspended member cannot be added as approver; nothing
    written (verifier finding #6).
    Rules: add_approver R2 (boundary)."""
    m = member_of(db, w1, u3)
    m.status = "suspended"
    db.flush()
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O_aa, w1, u3, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert approver_row(db, O_aa.id, u3.id) is None
    assert events_of(db, O_aa.id) == []


def test_eo_aa_08__invited_member_rejected(db, M, w1, O_aa, u1, u3):
    """EO-AA-08 -- an invited (not yet active) member cannot be added as
    approver; nothing written (verifier finding #6).
    Rules: add_approver R2 (boundary)."""
    m = member_of(db, w1, u3)
    m.status = "invited"
    db.flush()
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O_aa, w1, u3, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert approver_row(db, O_aa.id, u3.id) is None
    assert events_of(db, O_aa.id) == []


def test_eo_aa_09__other_workspace_member_rejected(db, M, w1, O_aa, u1, u4):
    """EO-AA-09 -- a user active only in another workspace cannot be added
    here; nothing written (verifier finding #6).
    Rules: add_approver R2 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O_aa, w1, u4, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert approver_row(db, O_aa.id, u4.id) is None
    assert events_of(db, O_aa.id) == []


def test_eo_aa_10__duplicate_approver_rejected(db, M, w1, O_aa, u1):
    """EO-AA-10 -- adding an existing approver again raises 409.
    Rules: add_approver R3 (error)."""
    with pytest.raises(HTTPException) as exc:
        aa(db, M, O_aa, w1, u1, u1)
    assert exc.value.status_code == 409
    assert exc.value.detail == "User is already an approver for this order"
    assert len(approvers_of(db, O_aa.id)) == 1
    assert events_of(db, O_aa.id) == []


# --------------------------------------------------------------------------- #
# `remove_approver`
# --------------------------------------------------------------------------- #
# O_rap = default order with approvers U1 approved and U3 pending.

@pytest.fixture
def O_rap(O, u1, u3, approver_factory):
    o = O()
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    return o


def test_eo_rap_01__happy_removes_approver_logs_event(db, M, w1, O_rap, u1, u3):
    """EO-RAP-01 -- removing an approver deletes the row and logs the event.
    Rules: remove_approver R2, R3, R4 (happy)."""
    result = M.remove_approver(db, O_rap.id, u3.id, w1.id, performed_by=u1.id)
    assert result is None
    assert approver_row(db, O_rap.id, u3.id) is None
    u1_row = approver_row(db, O_rap.id, u1.id)
    assert u1_row.approved is True and u1_row.approved_at == T0
    evs = events_of(db, O_rap.id)
    assert events_as_pairs(evs) == [E("approver_removed", "Removed Rahim Uddin as approver")]
    assert evs[0].performed_by == u1.id
    assert evs[0].metadata_json == {"user_id": u3.id, "user_name": "Rahim Uddin"}


def test_eo_rap_02__no_performed_by_defaults_none(db, M, w1, O_rap, u3):
    """EO-RAP-02 -- performed_by defaults to None when not supplied.
    Rules: remove_approver R3 (boundary)."""
    result = M.remove_approver(db, O_rap.id, u3.id, w1.id)
    assert result is None
    evs = events_of(db, O_rap.id)
    assert evs[0].performed_by is None


def test_eo_rap_03__not_an_approver_404(db, M, w1, O_rap, u1, u2):
    """EO-RAP-03 -- removing a user who is not an approver raises 404.
    Rules: remove_approver R1 (error)."""
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, O_rap.id, u2.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert len(approvers_of(db, O_rap.id)) == 2
    assert events_of(db, O_rap.id) == []


def test_eo_rap_04__missing_order_id_still_approver_not_found(db, M, w1, O_rap, u1):
    """EO-RAP-04 -- an unknown order id also surfaces as 'Approver not found'
    (the approver lookup runs before any order lookup).
    Rules: remove_approver R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, missing, u1.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert len(approvers_of(db, O_rap.id)) == 2
    assert events_of(db, O_rap.id) == []


def test_eo_rap_05__other_workspace_approver_not_found(db, M, w1, O5, u4, approver_factory):
    """EO-RAP-05 -- another workspace's approver row is not found here.
    Rules: remove_approver R1 (isolation)."""
    approver_factory(O5, u4, assigned_by=u4)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, O5.id, u4.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert approver_row(db, O5.id, u4.id) is not None


@pytest.mark.xfail(strict=True, reason=BUG_756 + " -- fails today on: row deleted")
def test_eo_rap_06__bug_756_completed_rejected(db, M, w1, O, u1, u3, approver_factory):
    """EO-RAP-06 -- a completed order must reject removing an approver.
    Rules: remove_approver R1 [BUG-756]."""
    o = O(completed_at=T0)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, o.id, u1.id, w1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is complete"
    assert approver_row(db, o.id, u1.id) is not None
    assert events_of(db, o.id) == []


def test_eo_rap_07__completed_but_not_approver_still_404(db, M, w1, O, u1, u3, u2, approver_factory):
    """EO-RAP-07 -- the approver-not-found check runs before any completed-order check.
    Rules: remove_approver R1 (boundary)."""
    o = O(completed_at=T0)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, o.id, u2.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"


def test_eo_rap_08__voided_order_removal_allowed(db, M, w1, O, u1, u3, approver_factory):
    """EO-RAP-08 -- a voided order still allows removing an approver (no voided guard here).
    Rules: remove_approver R1 (soft-delete)."""
    o = O(voided=True)
    approver_factory(o, u1, assigned_by=u1, approved=True, approved_at=T0)
    approver_factory(o, u3, assigned_by=u1, approved=False)
    result = M.remove_approver(db, o.id, u3.id, w1.id)
    assert result is None
    assert approver_row(db, o.id, u3.id) is None
    evs = events_of(db, o.id)
    assert len(evs) == 1 and evs[0].event_type == "approver_removed"


# --------------------------------------------------------------------------- #
# `set_approval`
# --------------------------------------------------------------------------- #
# O_sa = ready order R with approver U2 pending; O_sa_approved = same with U2
# already approved. "sa(u, v)" = set_approval(db, o.id, u.id, w1.id, approved=v).

@pytest.fixture
def O_sa(R, u1, u2, approver_factory):
    o = R()
    approver_factory(o, u2, assigned_by=u1, approved=False)
    return o


@pytest.fixture
def O_sa_approved(R, u1, u2, approver_factory):
    o = R()
    approver_factory(o, u2, assigned_by=u1, approved=True, approved_at=T0)
    return o


def sa(db, M, o, w1, user, approved):
    return M.set_approval(db, o.id, user.id, w1.id, approved=approved)


def test_eo_sa_01__approve_happy(db, M, w1, O_sa, u2):
    """EO-SA-01 -- approving sets approved/approved_at and logs the event.
    Rules: set_approval R6 (happy)."""
    row = sa(db, M, O_sa, w1, u2, True)
    assert row.user_id == u2.id
    r = reread_approver(db, row.id)
    assert r.approved is True and r.approved_at == NOW
    evs = events_of(db, O_sa.id)
    assert events_as_pairs(evs) == [E("approved", "Approved expense order")]
    assert evs[0].performed_by == u2.id


def test_eo_sa_02__withdraw_happy(db, M, w1, O_sa_approved, u2):
    """EO-SA-02 -- withdrawing clears approved/approved_at and logs the event.
    Rules: set_approval R7 (happy)."""
    row = sa(db, M, O_sa_approved, w1, u2, False)
    r = reread_approver(db, row.id)
    assert r.approved is False and r.approved_at is None
    evs = events_of(db, O_sa_approved.id)
    assert events_as_pairs(evs) == [E("approval_withdrawn", "Withdrew approval")]
    assert evs[0].performed_by == u2.id


def test_eo_sa_03__not_an_approver_403(db, M, w1, O_sa, u3):
    """EO-SA-03 -- a user with no approver row for this order cannot set approval.
    Rules: set_approval R1 (error)."""
    before = order_snap(db, O_sa.id)
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u3, True)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not an assigned approver for this order"
    assert order_snap(db, O_sa.id) == before
    assert events_of(db, O_sa.id) == []


def test_eo_sa_04__missing_order_still_403(db, M, w1, O_sa, u2):
    """EO-SA-04 -- an unknown order id also surfaces as 'not an assigned approver'
    (the approver lookup runs before any order lookup).
    Rules: set_approval R1 (boundary)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, missing, u2.id, w1.id, approved=True)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not an assigned approver for this order"
    assert approver_row(db, O_sa.id, u2.id).approved is False
    assert events_of(db, O_sa.id) == []


def test_eo_sa_05__other_workspace_403(db, M, w1, O5, u4, approver_factory):
    """EO-SA-05 -- another workspace's approver row is not visible here.
    Rules: set_approval R1 (isolation)."""
    approver_factory(O5, u4, assigned_by=u4)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, O5.id, u4.id, w1.id, approved=True)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not an assigned approver for this order"
    assert approver_row(db, O5.id, u4.id).approved is False


def test_eo_sa_06__inconsistent_workspace_data_404(db, M, w1, O5, u2, approver_factory):
    """EO-SA-06 -- an approver row stamped with the wrong workspace surfaces the
    order's real 404 (not the 403 for a missing approver row).
    Rules: set_approval R2 (error)."""
    approver_factory(O5, u2, assigned_by=u2, workspace_id=w1.id)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, O5.id, u2.id, w1.id, approved=True)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)
    assert approver_row(db, O5.id, u2.id).approved is False


def test_eo_sa_07__completed_order_still_approvable(db, M, w1, O_sa, u2):
    """EO-SA-07 -- a completed order can still record an approval (no completed
    guard on approve). Re-read from the DB rather than the in-memory returned
    object (verifier finding #8).
    Rules: set_approval R3 (boundary)."""
    O_sa.completed_at = T0
    db.flush()
    row = sa(db, M, O_sa, w1, u2, True)
    assert reread_approver(db, row.id).approved is True


@pytest.mark.xfail(strict=True, reason=BUG_754 + " -- fails today on: approval recorded")
def test_eo_sa_08__bug_754_voided_rejected(db, M, w1, O_sa, u2):
    """EO-SA-08 -- a voided order must reject recording an approval.
    Rules: set_approval R4 [BUG-754]."""
    O_sa.voided = True
    db.flush()
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u2, True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Expense order is voided"
    assert approver_row(db, O_sa.id, u2.id).approved is False


def test_eo_sa_09__not_ready_description_blank(db, M, w1, O_sa, u2):
    """EO-SA-09 -- approving a not-ready order surfaces the readiness gap
    reason; nothing written (verifier finding #6: previous pass did not check
    events).
    Rules: set_approval R4 (error)."""
    O_sa.description = "   "
    db.flush()
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u2, True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Add a description before approvals can proceed"
    assert approver_row(db, O_sa.id, u2.id).approved is False
    assert events_of(db, O_sa.id) == []


def test_eo_sa_10__not_ready_no_lines(db, M, w1, O_sa, u2):
    """EO-SA-10 -- approving an order with no lines surfaces the no-lines
    reason; nothing written (verifier finding #6: the previous pass asserted
    nothing besides the status code).
    Rules: set_approval R4 (error)."""
    for item in lines_of(db, O_sa.id):
        db.delete(item)
    db.flush()
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u2, True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Add at least one expense line before approvals can proceed"
    assert approver_row(db, O_sa.id, u2.id).approved is False
    assert events_of(db, O_sa.id) == []


def test_eo_sa_11__not_ready_line_zero_quantity(db, M, w1, O_sa, u2, line_factory):
    """EO-SA-11 -- approving an order with a zero-quantity line is rejected
    (status only; the detail text is BUG-758, asserted separately by SA-12);
    nothing written (verifier finding #6: previous pass did not check events).
    Rules: set_approval R4 (error)."""
    line_factory(O_sa, 2, description="Water", quantity=Decimal("0"))
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u2, True)
    assert exc.value.status_code == 400
    assert approver_row(db, O_sa.id, u2.id).approved is False
    assert events_of(db, O_sa.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_758 + " -- fails today on: detail is 'Order is not ready for approval'")
def test_eo_sa_12__bug_758_line_level_gap_message(db, M, w1, O_sa, u2, line_factory):
    """EO-SA-12 -- the not-ready detail should name the line-level problem.
    Rules: set_approval R4 [BUG-758]."""
    line_factory(O_sa, 2, description="Water", quantity=Decimal("0"))
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa, w1, u2, True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Every expense line needs a description and a quantity above 0 before approvals can proceed"
    assert approver_row(db, O_sa.id, u2.id).approved is False


@pytest.mark.xfail(strict=True, reason=BUG_744 + " -- fails today on: no captured FOR UPDATE")
def test_eo_sa_13__bug_744_locks_order_row_on_approve(db, M, w1, O_sa, u2, engine):
    """EO-SA-13 -- approving should read the order row FOR UPDATE.
    Rules: set_approval R4 [BUG-744]."""
    with SQLCapture(engine) as cap:
        sa(db, M, O_sa, w1, u2, True)
    assert cap.locked


@pytest.mark.xfail(strict=True, reason=BUG_744 + " -- fails today on: no captured FOR UPDATE")
def test_eo_sa_14__bug_744_locks_order_row_on_withdraw(db, M, w1, O_sa_approved, u2, engine):
    """EO-SA-14 -- withdrawing should also read the order row FOR UPDATE.
    Rules: set_approval R5 [BUG-744]."""
    with SQLCapture(engine) as cap:
        sa(db, M, O_sa_approved, w1, u2, False)
    assert cap.locked


def test_eo_sa_15__withdraw_rejected_when_completed(db, M, w1, O_sa_approved, u2):
    """EO-SA-15 -- withdrawing approval on a completed order is rejected.
    Rules: set_approval R5 (error)."""
    O_sa_approved.completed_at = T0
    db.flush()
    with pytest.raises(HTTPException) as exc:
        sa(db, M, O_sa_approved, w1, u2, False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot withdraw approval — order is complete"
    r = approver_row(db, O_sa_approved.id, u2.id)
    assert r.approved is True and r.approved_at == T0
    assert events_of(db, O_sa_approved.id) == []


def test_eo_sa_16__withdraw_allowed_on_voided_order(db, M, w1, O_sa_approved, u2):
    """EO-SA-16 -- a voided order still allows withdrawing an approval (no
    voided guard here). Re-read from the DB rather than the in-memory
    returned object (verifier finding #8).
    Rules: set_approval R3, R7 (soft-delete)."""
    O_sa_approved.voided = True
    db.flush()
    row = sa(db, M, O_sa_approved, w1, u2, False)
    assert reread_approver(db, row.id).approved is False
    evs = events_of(db, O_sa_approved.id)
    assert len(evs) == 1 and evs[0].event_type == "approval_withdrawn"


def test_eo_sa_17__withdraw_ignores_readiness(db, M, w1, O_sa_approved, u2):
    """EO-SA-17 -- withdrawing does not check readiness. Re-read from the DB
    rather than the in-memory returned object (verifier finding #8).
    Rules: set_approval R7 (boundary)."""
    O_sa_approved.description = None
    db.flush()
    row = sa(db, M, O_sa_approved, w1, u2, False)
    assert reread_approver(db, row.id).approved is False


@pytest.mark.xfail(strict=True, reason=BUG_757 + " -- fails today on: approved_at == NOW")
def test_eo_sa_18__bug_757_reapprove_is_noop(db, M, w1, O_sa_approved, u2):
    """EO-SA-18 -- re-approving an already-approved user should be a no-op.
    Rules: set_approval R6 [BUG-757]."""
    row = sa(db, M, O_sa_approved, w1, u2, True)
    r = reread_approver(db, row.id)
    assert r.approved is True and r.approved_at == T0
    assert events_of(db, O_sa_approved.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_757 + " -- fails today on: 1 approval_withdrawn event")
def test_eo_sa_19__bug_757_withdraw_pending_is_noop(db, M, w1, O_sa, u2):
    """EO-SA-19 -- withdrawing a never-approved pending approver should log nothing.
    Rules: set_approval R7 [BUG-757]."""
    row = sa(db, M, O_sa, w1, u2, False)
    assert row.approved is False
    assert events_of(db, O_sa.id) == []


def test_eo_sa_20__reapprove_still_approved(db, M, w1, O_sa_approved, u2):
    """EO-SA-20 -- re-approving leaves the row approved (true today and after the BUG-757 fix).
    Rules: set_approval R6 (boundary)."""
    row = sa(db, M, O_sa_approved, w1, u2, True)
    r = reread_approver(db, row.id)
    assert r.approved is True


def test_eo_sa_21__only_acting_approver_changed(db, M, w1, O_sa, u1, u3, u2, approver_factory):
    """EO-SA-21 -- approving affects only the acting user's row.
    Rules: set_approval R6 (isolation)."""
    approver_factory(O_sa, u3, assigned_by=u1, approved=False)
    row = sa(db, M, O_sa, w1, u2, True)
    assert row.user_id == u2.id
    u3_row = approver_row(db, O_sa.id, u3.id)
    assert u3_row.approved is False


def test_eo_sa_22__withdraw_pending_stays_pending(db, M, w1, O_sa, u2):
    """EO-SA-22 -- withdrawing a pending approver leaves it pending
    (true today and after the BUG-757 fix; pass partner of SA-19).
    Rules: set_approval R7 (boundary)."""
    row = sa(db, M, O_sa, w1, u2, False)
    r = reread_approver(db, row.id)
    assert r.approved is False and r.approved_at is None


# --------------------------------------------------------------------------- #
# `log_event`
# --------------------------------------------------------------------------- #

def test_eo_le_01__happy_logs_event(db, M, w1, O, u2):
    """EO-LE-01 -- logging an event stores all fields and stamps created_at from
    the column default (real-clock window).
    Rules: log_event R1 (happy)."""
    o = O()
    real_utcnow = real_window()
    before = real_utcnow()
    ev = M.log_event(db, o.id, w1.id, "note", "Called vendor", performed_by=u2.id, metadata={"k": 1})
    after = real_utcnow()
    assert ev.id is not None
    r = reread_event(db, ev.id)
    assert r.workspace_id == w1.id
    assert r.expense_order_id == o.id
    assert r.event_type == "note"
    assert r.description == "Called vendor"
    assert r.performed_by == u2.id
    assert r.metadata_json == {"k": 1}
    assert before <= r.created_at <= after


def test_eo_le_02__defaults_performed_by_and_metadata_none(db, M, w1, O):
    """EO-LE-02 -- performed_by and metadata default to None.
    Rules: log_event R1 (boundary)."""
    o = O()
    ev = M.log_event(db, o.id, w1.id, "note", "x")
    r = reread_event(db, ev.id)
    assert r.performed_by is None
    assert r.metadata_json is None


def test_eo_le_03__workspace_id_not_cross_checked(db, M, w1, w2, O):
    """EO-LE-03 -- log_event does not check that the order belongs to the given workspace.
    Rules: log_event R2 (boundary)."""
    o = O()
    ev = M.log_event(db, o.id, w2.id, "note", "x")
    r = reread_event(db, ev.id)
    assert r.workspace_id == w2.id
    assert r.expense_order_id == o.id


def test_eo_le_04__missing_order_id_integrity_error(db, M, w1):
    """EO-LE-04 -- an unknown order id violates the FK at flush.
    Rules: log_event R2 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            M.log_event(db, missing, w1.id, "note", "x")
    assert events_of(db, missing) == []


def test_eo_le_05__event_type_boundary_50_chars(db, M, w1, O):
    """EO-LE-05 -- a 50-character event_type is accepted (column limit).
    Rules: log_event R2 (boundary)."""
    o = O()
    ev = M.log_event(db, o.id, w1.id, "e" * 50, "x")
    r = reread_event(db, ev.id)
    assert r.event_type == "e" * 50


def test_eo_le_06__event_type_too_long_dbapi_error(db, M, w1, O):
    """EO-LE-06 -- a 51-character event_type exceeds the column limit at flush
    (best-practice default, delegated by reviewer: any DBAPIError subclass accepted).
    Rules: log_event R2 (error)."""
    o = O()
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            M.log_event(db, o.id, w1.id, "e" * 51, "x")
    assert events_of(db, o.id) == []


# --------------------------------------------------------------------------- #
# `list_events`
# --------------------------------------------------------------------------- #

def test_eo_lv_01__ordered_desc_with_profiles(db, M, w1, O, u1, u2, event_factory):
    """EO-LV-01 -- events ordered by created_at desc, each paired with the performer's profile.
    Rules: list_events R2, R3 (happy)."""
    o = O()
    e1 = event_factory(o, "note", "a", performed_by=u1, created_at=T0)
    e2 = event_factory(o, "note", "b", performed_by=u2, created_at=T0 + timedelta(hours=2))
    e3 = event_factory(o, "note", "c", performed_by=None, created_at=T0 + timedelta(hours=1))
    result = M.list_events(db, o.id, w1.id)
    assert [r[0].id for r in result] == [e2.id, e3.id, e1.id]
    assert result[0][1].id == u2.id
    assert result[1][1] is None
    assert result[2][1].id == u1.id


def test_eo_lv_02__same_timestamp_tiebreak_by_id_desc(db, M, w1, O, event_factory):
    """EO-LV-02 -- events with equal created_at are tie-broken by id descending.
    Rules: list_events R2 (boundary)."""
    o = O()
    e1 = event_factory(o, "note", "a", created_at=T0)
    e2 = event_factory(o, "note", "b", created_at=T0)
    result = M.list_events(db, o.id, w1.id)
    assert [r[0].id for r in result] == [e2.id, e1.id]


def test_eo_lv_03__no_events_empty_list(db, M, w1, O):
    """EO-LV-03 -- an order with no events returns [].
    Rules: list_events R2 (boundary)."""
    o = O()
    assert M.list_events(db, o.id, w1.id) == []


def test_eo_lv_04__isolation_other_order_events_excluded(db, M, w1, O, event_factory):
    """EO-LV-04 -- another order's events are not included.
    Rules: list_events R2 (isolation)."""
    o = O()
    p = O()
    e1 = event_factory(o, "note", "a")
    event_factory(p, "note", "z")
    result = M.list_events(db, o.id, w1.id)
    assert [r[0].id for r in result] == [e1.id]


def test_eo_lv_05__missing_order_404(db, M, w1):
    """EO-LV-05 -- an unknown order id raises 404.
    Rules: list_events R1 (error)."""
    missing = missing_id(db, ExpenseOrder)
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(missing)


def test_eo_lv_06__other_workspace_404(db, M, w1, O5):
    """EO-LV-06 -- another workspace's order raises 404.
    Rules: list_events R1 (isolation)."""
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, O5.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_order(O5.id)


def test_eo_lv_07__performer_profile_deleted_shows_as_none(db, M, w1, O, event_factory):
    """EO-LV-07 -- a deleted performer profile leaves performed_by null (FK ON DELETE SET NULL).
    Rules: list_events R3 (boundary)."""
    performer = make_profile(db, name="Temp Performer")
    o = O()
    e1 = event_factory(o, "note", "a", performed_by=performer)
    db.delete(db.get(Profile, performer.id))
    db.flush()
    result = M.list_events(db, o.id, w1.id)
    assert [r[0].id for r in result] == [e1.id]
    assert result[0][1] is None
    assert reread_event(db, e1.id).performed_by is None


# --------------------------------------------------------------------------- #
# `create_expense_order_from_template`
# --------------------------------------------------------------------------- #
# TPL = template of W1: "Monthly rent" / "Rent for the plant", category factory,
# cost center F1, account A1, is_active, requires_approval=True, auto_approve=False,
# default_approver_id=None. tpl_lines adds lines 5 ("Service") then 2 ("Rent").
# "ft(tpl, **o)" = create_expense_order_from_template(db, tpl.id, w1.id, u1.id,
# ExpenseOrderFromTemplateCreate(**o)).

@pytest.fixture
def TPL(template_factory, w1, f1, a1):
    return template_factory(w1, account_id=a1.id, cost_center_id=f1.id)


@pytest.fixture
def tpl_lines(TPL, template_item_factory):
    template_item_factory(TPL, 5, description="Service", quantity=Decimal("2"), unit="month", unit_price=Decimal("250.00"), notes="svc")
    template_item_factory(TPL, 2, description="Rent", quantity=Decimal("1"), unit_price=Decimal("5000.00"))
    return TPL


def ft(db, M, tpl, w1, u1, **over):
    return M.create_expense_order_from_template(db, tpl.id, w1.id, u1.id, ExpenseOrderFromTemplateCreate(**over))


def test_eo_t_01__full_happy_path(db, M, w1, u1, tpl_lines):
    """EO-T-01 -- creating from a fully-specified template builds the order, lines
    (sorted by template line_number), approver and both events.
    Rules: create_expense_order_from_template R3, R4, R7, R9, R10 (happy)."""
    year = datetime.now().year
    eo = ft(db, M, tpl_lines, w1, u1, expense_date=date(2026, 4, 1), due_date=date(2026, 4, 30))
    o = reread_order(db, eo.id)
    assert o.account_id == tpl_lines.account_id
    assert o.expense_category == "factory"
    assert o.cost_center_id == tpl_lines.cost_center_id
    assert o.expense_date == date(2026, 4, 1)
    assert o.due_date == date(2026, 4, 30)
    assert o.description == "Rent for the plant"
    assert o.order_template_id == tpl_lines.id
    assert o.required_approvals is None
    assert o.expense_number == f"EXP-{year}-001"
    lines = {ln.line_number: ln for ln in lines_of(db, eo.id)}
    assert lines[1].description == "Rent" and lines[1].quantity == 1 and lines[1].unit_price == Decimal("5000.00") and lines[1].line_subtotal == Decimal("5000.00")
    assert lines[2].description == "Service" and lines[2].quantity == 2 and lines[2].unit == "month" and lines[2].notes == "svc" and lines[2].unit_price == Decimal("250.00") and lines[2].line_subtotal == Decimal("500.00")
    assert o.subtotal == Decimal("5500.00") and o.total_amount == Decimal("5500.00")
    approvers = approvers_of(db, eo.id)
    assert len(approvers) == 1 and approvers[0].user_id == u1.id and approvers[0].approved is False
    evs = events_of(db, eo.id)
    assert events_as_pairs(evs) == [
        E("created", "Expense order created"),
        E("created_from_template", 'Generated from template "Monthly rent"'),
    ]
    assert evs[1].metadata_json == {"order_template_id": tpl_lines.id}
    assert evs[1].performed_by == u1.id


def test_eo_t_02__missing_template_404(db, M, w1, u1):
    """EO-T-02 -- an unknown template id raises 404 and creates nothing.
    Rules: create_expense_order_from_template R1 (error)."""
    missing = missing_id(db, OrderTemplate)
    with pytest.raises(HTTPException) as exc:
        ft(db, M, SimpleNamespace(id=missing), w1, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {missing} not found"
    assert ws_order_count(db, w1.id) == 0


def test_eo_t_03__other_workspace_template_404(db, M, w1, w2, u1, template_factory):
    """EO-T-03 -- a template belonging to another workspace raises 404.
    Rules: create_expense_order_from_template R1 (isolation)."""
    tw2 = template_factory(w2)
    with pytest.raises(HTTPException) as exc:
        ft(db, M, tw2, w1, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {tw2.id} not found"
    assert ws_order_count(db, w1.id) == 0


def test_eo_t_04__inactive_template_rejected(db, M, w1, u1, TPL):
    """EO-T-04 -- an inactive template cannot generate an order.
    Rules: create_expense_order_from_template R2 (error)."""
    TPL.is_active = False
    db.flush()
    with pytest.raises(HTTPException) as exc:
        ft(db, M, TPL, w1, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Template is inactive"
    assert ws_order_count(db, w1.id) == 0


def test_eo_t_05__defaults_expense_date_today_no_due_date(db, M, w1, u1, TPL):
    """EO-T-05 -- with no override, expense_date defaults to today and due_date is null.
    Rules: create_expense_order_from_template R3 (boundary)."""
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.expense_date == date.today()
    assert o.due_date is None


def test_eo_t_06__description_override_used(db, M, w1, u1, TPL):
    """EO-T-06 -- a non-empty description override replaces the template's.
    Rules: create_expense_order_from_template R3 (boundary)."""
    eo = ft(db, M, TPL, w1, u1, description="April rent")
    assert reread_order(db, eo.id).description == "April rent"


def test_eo_t_07__empty_description_falls_back_to_template(db, M, w1, u1, TPL):
    """EO-T-07 -- an empty-string override is falsy and falls back to the template's description.
    Rules: create_expense_order_from_template R3 (boundary)."""
    eo = ft(db, M, TPL, w1, u1, description="")
    assert reread_order(db, eo.id).description == "Rent for the plant"


def test_eo_t_08__none_category_defaults_other(db, M, w1, u1, TPL):
    """EO-T-08 -- a null template category defaults to 'other'.
    Rules: create_expense_order_from_template R3 (boundary)."""
    TPL.expense_category = None
    TPL.cost_center_id = None
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.expense_category == "other"
    assert o.cost_center_id is None


def test_eo_t_09__blank_category_defaults_other(db, M, w1, u1, TPL):
    """EO-T-09 -- a blank template category also defaults to 'other'.
    Rules: create_expense_order_from_template R3 (boundary)."""
    TPL.expense_category = ""
    TPL.cost_center_id = None
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    assert reread_order(db, eo.id).expense_category == "other"


@pytest.mark.xfail(strict=True, reason=BUG_752 + " -- fails today on: cost_center_id == F1.id")
def test_eo_t_10__bug_752_other_category_keeps_stale_cost_center(db, M, w1, u1, f1, TPL):
    """EO-T-10 -- defaulting to 'other' should clear a stale cost_center_id.
    Rules: create_expense_order_from_template R3 [BUG-752]."""
    TPL.expense_category = None
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.expense_category == "other"
    assert o.cost_center_id is None


def test_eo_t_11__none_template_description_rejected(db, M, w1, u1, TPL):
    """EO-T-11 -- a template with no description and no override is rejected.
    Rules: create_expense_order_from_template R3, create_expense_order R2 (error)."""
    TPL.description = None
    db.flush()
    with pytest.raises(HTTPException) as exc:
        ft(db, M, TPL, w1, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert ws_order_count(db, w1.id) == 0


def test_eo_t_12__other_workspace_cost_center_rejected(db, M, w1, u1, f2, TPL):
    """EO-T-12 -- a template cost-center id from another workspace fails the allocation check.
    Rules: create_expense_order_from_template R3, create_expense_order R1 (error)."""
    TPL.cost_center_id = f2.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        ft(db, M, TPL, w1, u1)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Selected factory not found"
    assert ws_order_count(db, w1.id) == 0


def test_eo_t_13__requires_approval_false_zero_required(db, M, w1, u1, TPL):
    """EO-T-13 -- requires_approval=False waives approval without logging auto_approved.
    Rules: create_expense_order_from_template R5, R9, R10 (happy)."""
    TPL.requires_approval = False
    TPL.auto_approve = True
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.required_approvals == 0
    approvers = approvers_of(db, eo.id)
    assert len(approvers) == 1 and approvers[0].user_id == u1.id and approvers[0].approved is False
    evs = events_of(db, eo.id)
    assert events_as_pairs(evs) == [
        E("created", "Expense order created"),
        E("created_from_template", 'Generated from template "Monthly rent"'),
    ]


def test_eo_t_14__requires_approval_true_auto_approve_logs_event(db, M, w1, u1, TPL):
    """EO-T-14 -- requires_approval=True with auto_approve=True waives approval and logs auto_approved.
    Rules: create_expense_order_from_template R6, R9, R10 (happy)."""
    TPL.requires_approval = True
    TPL.auto_approve = True
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.required_approvals == 0
    approvers = approvers_of(db, eo.id)
    assert len(approvers) == 1 and approvers[0].user_id == u1.id
    evs = events_of(db, eo.id)
    assert events_as_pairs(evs) == [
        E("created", "Expense order created"),
        E("auto_approved", "Auto-approved — following template instructions"),
        E("created_from_template", 'Generated from template "Monthly rent"'),
    ]
    assert evs[1].metadata_json == {"order_template_id": TPL.id}
    assert evs[1].performed_by == u1.id


def test_eo_t_15__default_approver_added(db, M, w1, u1, u3, TPL):
    """EO-T-15 -- a live, distinct default approver is added as a second approver.
    Rules: create_expense_order_from_template R7, R9 (happy)."""
    TPL.default_approver_id = u3.id
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.required_approvals is None
    approvers = {a.user_id: a for a in approvers_of(db, eo.id)}
    assert set(approvers) == {u1.id, u3.id}
    assert approvers[u3.id].assigned_by == u1.id
    assert approvers[u3.id].approved is False
    evs = events_of(db, eo.id)
    assert events_as_pairs(evs) == [
        E("created", "Expense order created"),
        E("approver_added", "Added Rahim Uddin as approver"),
        E("created_from_template", 'Generated from template "Monthly rent"'),
    ]
    assert evs[1].performed_by == u1.id


def test_eo_t_16__default_approver_is_creator_no_duplicate(db, M, w1, u1, TPL):
    """EO-T-16 -- when the default approver is the creator, no second approver is added.
    Rules: create_expense_order_from_template R7 (boundary)."""
    TPL.default_approver_id = u1.id
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    approvers = approvers_of(db, eo.id)
    assert [a.user_id for a in approvers] == [u1.id]
    evs = events_of(db, eo.id)
    assert "approver_added" not in [e.event_type for e in evs]


@pytest.mark.xfail(strict=True, reason=BUG_759 + " -- fails today on: 400 User is not an active member of this workspace raised")
def test_eo_t_17__bug_759_suspended_default_approver_skipped(db, M, w1, u1, u3, TPL):
    """EO-T-17 -- a suspended default approver should be skipped, not fail the whole create.
    Rules: create_expense_order_from_template R8 [BUG-759]."""
    m = member_of(db, w1, u3)
    m.status = "suspended"
    TPL.default_approver_id = u3.id
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    approvers = approvers_of(db, eo.id)
    assert [a.user_id for a in approvers] == [u1.id]
    evs = events_of(db, eo.id)
    assert events_as_pairs(evs) == [
        E("created", "Expense order created"),
        E("default_approver_skipped", "Default approver Rahim Uddin is not an active member and was skipped"),
        E("created_from_template", 'Generated from template "Monthly rent"'),
    ]
    assert evs[1].metadata_json == {"user_id": u3.id, "user_name": "Rahim Uddin"}
    assert evs[1].performed_by == u1.id


@pytest.mark.xfail(strict=True, reason=BUG_759 + " -- fails today on: 400 raised")
def test_eo_t_18__bug_759_other_workspace_default_approver_skipped(db, M, w1, u1, u4, TPL):
    """EO-T-18 -- a default approver who is not a member of this workspace at all is skipped.
    Rules: create_expense_order_from_template R8 [BUG-759]."""
    TPL.default_approver_id = u4.id
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    approvers = approvers_of(db, eo.id)
    assert [a.user_id for a in approvers] == [u1.id]
    evs = events_of(db, eo.id)
    assert [e.event_type for e in evs] == ["created", "default_approver_skipped", "created_from_template"]


def test_eo_t_19__no_template_lines(db, M, w1, u1, TPL):
    """EO-T-19 -- a template with no lines produces an order with zero totals.
    Rules: create_expense_order_from_template R4 (boundary)."""
    eo = ft(db, M, TPL, w1, u1)
    assert lines_of(db, eo.id) == []
    o = reread_order(db, eo.id)
    assert o.subtotal == 0 and o.total_amount == 0


def test_eo_t_20__whitespace_override_description_rejected(db, M, w1, u1, TPL):
    """EO-T-20 -- a whitespace-only override is truthy (not falsy), so it is used as given
    and rejected, instead of falling back to the template's description.
    Rules: create_expense_order_from_template R3, create_expense_order R2 (error)."""
    with pytest.raises(HTTPException) as exc:
        ft(db, M, TPL, w1, u1, description="   ")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Description is required"
    assert ws_counts(db, w1.id) == (0, 0, 0, 0)


def test_eo_t_21__other_category_with_stale_cost_center_builds_ok(db, M, w1, u1, f1, TPL):
    """EO-T-21 -- defaulting to 'other' with a stale template cost_center_id still builds
    successfully today (holds before and after the BUG-752 fix; pass partner of T-10).
    Rules: create_expense_order_from_template R3, _validate_order_allocation R2 (boundary)."""
    TPL.expense_category = None
    db.flush()
    eo = ft(db, M, TPL, w1, u1)
    o = reread_order(db, eo.id)
    assert o.expense_category == "other"
    assert o.order_template_id == TPL.id
