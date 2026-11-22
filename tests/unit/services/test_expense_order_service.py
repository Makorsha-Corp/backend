# ruff: noqa: SIM117, DTZ001, B017, FURB157
# (nested `with` blocks, naive datetimes, `pytest.raises(Exception)` and
# `Decimal("1")`-style literals are prescribed by the cards' Conventions.)
"""Unit tests for app/services/expense_order_service.py.

Implements tests/unit/services/expense_order_service.cases.md (revision 4,
2026-11-22), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: `utcnow` in the service and the manager
(autouse fixture `clock`, NOW naive like the real helper); the commit /
rollback / refresh spies and failing variants (`patch.object(db, ...)`); the
notification functions imported by name into the service ("failing notify",
"failing section notify", "failing approver notify"); and the two
`create_invoice` spies of D-12 / D-14. Nothing else is mocked; the lock cards
record the SQL sent with an `after_cursor_execute` listener.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.U2`,
`s.A1`). `# Then N` marks the checks of the card's Then line N.
"""

import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text

from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.department import Department
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.notification import Notification
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.expense_order import (
    ExpenseOrderCreate,
    ExpenseOrderFromTemplateCreate,
    ExpenseOrderHubStatsResponse,
    ExpenseOrderItemCreate,
    ExpenseOrderItemUpdate,
    ExpenseOrderListResponse,
    ExpenseOrderUpdate,
    ExpenseOrderVoidRequest,
)
from app.schemas.order_hub import OrderHubRecentSummary
from app.services.expense_order_service import (
    ExpenseOrderService,
    expense_order_service,
)
from app.services.order_hub_stats_helpers import expense_order_to_recent_summary
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = expense_order_service
mgr = svc.manager
assert isinstance(svc, ExpenseOrderService)

MISSING = 999999999
T0 = datetime(2026, 9, 1, 8, 0)
T1 = datetime(2026, 9, 2, 9, 0)
T2 = datetime(2026, 9, 3, 10, 0)
NOW = datetime(2026, 9, 27, 12, 0, 0)

NOTMET = "Required approvals are not met"
NOINV = "No invoice linked — set an account so a draft invoice can be created, then try again"
VOIDINV = "Linked invoice was voided — cannot complete this order"
RESETMSG = "Approvals were reset — order details changed; re-approve when ready"
RESETVOID = "Cleared approvals — expense order voided (1 approval(s) cleared)"
SKIPMSG = "Approvals met but no account set — set an account to generate the invoice"
DRAFTP = "draft|Linked payable invoice is in draft — confirm when details look correct"
CLEARACC = "An invoice is linked to this order — choose another account instead of clearing it"
PAYHIST = "Invoice has payment history — confirm and void it instead"
FINAL = (
    "This order's invoice is already finalized. Void the invoice on the invoice"
    " page first, then void the order."
)

_BUGS = {
    627: "Invoice amount entered at creation is silently discarded at confirmation",
    628: "Invoice with no line items can be confirmed",
    629: "Moving a draft invoice to another account skips create's account checks",
    639: "A draft that once had (voided) payments cannot be deleted",
    742: "delete_expense_order deletes without a row lock and leaves a linked invoice behind",
    755: "Order with no approvers and no explicit requirement counts as fully approved",
    1193: "Deleted expense order vanishes without trace",
    3062: 'Complete, void and "create invoice" check the expense order without a row lock',
    3063: "The auto-drafted expense invoice is dated with the server's local date",
    3064: "A blank expense order void reason is accepted",
    3065: "A voided expense order can get a new invoice and then be completed",
    3066: "Removing a pending approver can complete the approvals, but no draft invoice is made",
    3067: "Voiding an expense order clears approvals only when it had an invoice",
    3068: "Clearing an expense order's account leaves its draft invoice on the old account",
    3069: "Voiding an expense order whose invoice is already finalized leaves a payable bill with no order",
    3070: "Voiding an expense order with a draft invoice logs the unlink event without the invoice id",
}


def xfail(n):
    """Expect `xfail BUG-n` -> strict xfail."""
    return pytest.mark.xfail(strict=True, reason=f"BUG-{n}: {_BUGS[n]}")


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Time: utcnow of the service and the manager return NOW (naive, like the real helper)
@pytest.fixture(autouse=True)
def clock():
    with patch("app.services.expense_order_service.utcnow", return_value=NOW):
        with patch("app.managers.expense_order_manager.utcnow", return_value=NOW):
            yield


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.TAG = uuid.uuid4().hex[:8]
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    for i, name in enumerate(
        ["Abid Hasan", "Karim Ali", "Rahim Uddin", "Nadia Khan", "Esha Roy"], 1
    ):
        setattr(n, f"U{i}", make_profile(db, name=name))
    for user, st in (
        (n.U1, "active"),
        (n.U2, "active"),
        (n.U3, "active"),
        (n.U4, "active"),
        (n.U5, "inactive"),
    ):
        _add(
            db,
            WorkspaceMember(
                workspace_id=n.W1.id, user_id=user.id, role="member", status=st
            ),
        )
    for key, ws, name in (
        ("A0", n.W0, "Zeta West"),
        ("A1", n.W1, "Acme Supplies"),
        ("A2", n.W1, "Beta Traders"),
        ("A9", n.W2, "Xeno Foreign"),
    ):
        setattr(
            n,
            key,
            _add(
                db,
                Account(
                    workspace_id=ws.id,
                    name=name,
                    is_active=True,
                    is_deleted=False,
                    allow_invoices=True,
                ),
            ),
        )
    n.DEP1 = _add(db, Department(workspace_id=n.W1.id, name="Admin", created_by=n.U1.id))
    return n


def _ws(s, ws):
    """'of W0' / 'of W2': the workspace and its account (ws = '0', '1', '2')."""
    return {"0": (s.W0, s.A0), "1": (s.W1, s.A1), "2": (s.W2, s.A9)}[ws]


# --------------------------------------------------------------------------- #
# Conventions -> Given rows ("but" = keyword overrides, applied last)
# --------------------------------------------------------------------------- #


# Convention 'acct "n"'
def acct(db, s, name, **but):
    fields = {
        "workspace_id": s.W1.id,
        "name": name,
        "is_active": True,
        "is_deleted": False,
        "allow_invoices": True,
    }
    fields.update(but)
    return _add(db, Account(**fields))


def _eo_obj(s, n, ws="1", waived=False, completed=False, voided=False, **but):
    w, a = _ws(s, ws)
    fields = {
        "workspace_id": w.id,
        "expense_number": f"EXP-{s.TAG}-{n}",
        "expense_category": "other",
        "expense_date": date(2026, 9, 1),
        "description": "Office rent",
        "account_id": a.id,
        "subtotal": Decimal("0.00"),
        "total_amount": Decimal("0.00"),
        "voided": False,
        "created_by": s.U1.id,
        "cost_center_id": None,
        "due_date": None,
        "required_approvals": None,
        "invoice_id": None,
        "completed_at": None,
        "completed_by": None,
        "updated_by": None,
        "voided_at": None,
        "voided_by": None,
        "void_note": None,
        "items_updated_at": None,
    }
    if waived:
        fields["required_approvals"] = 0
    if completed:
        fields.update(completed_at=T0, completed_by=s.U1.id, updated_by=s.U1.id)
    if voided:
        fields.update(voided=True, void_note="Duplicate", voided_at=T0, voided_by=s.U1.id)
    fields.update(but)
    return ExpenseOrder(**fields)


# Convention 'eo "n"' (ws "0"/"2" = of W0 / of W2; waived; completed; voided)
def eo(db, s, n, **kw):
    return _add(db, _eo_obj(s, n, **kw))


# Convention "N orders, by add_all and one flush"
def eo_many(db, s, count):
    rows = [_eo_obj(s, str(k)) for k in range(1, count + 1)]
    db.add_all(rows)
    db.flush()
    return rows


# Convention "line(E, k, s)"
def line(db, E, k, amount, **but):
    fields = {
        "workspace_id": E.workspace_id,
        "expense_order_id": E.id,
        "line_number": k,
        "description": f"Line {k}",
        "quantity": Decimal("1"),
        "unit": None,
        "unit_price": Decimal(amount),
        "line_subtotal": Decimal(amount),
    }
    fields.update(but)
    return _add(db, ExpenseOrderItem(**fields))


# Convention "appr(E, U)" (approved=True -> "approved")
def appr(db, s, E, U, approved=False):
    fields = {
        "workspace_id": E.workspace_id,
        "expense_order_id": E.id,
        "user_id": U.id,
        "assigned_by": s.U1.id,
        "approved": False,
        "approved_at": None,
        "assigned_at": T0,
    }
    if approved:
        fields.update(approved=True, approved_at=T0)
    return _add(db, ExpenseOrderApprover(**fields))


# Convention "inv(E)" / "inv(None)" (confirmed; voided-inv; ws "0"/"2"; linked)
def inv(db, s, E, ws="1", confirmed=False, voided_inv=False, linked=False, **but):
    w, a = _ws(s, ws)
    fields = {
        "workspace_id": w.id,
        "account_id": a.id,
        "invoice_type": "payable",
        "invoice_status": "draft",
        "payment_status": "unpaid",
        "invoice_amount": Decimal("0.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": date(2026, 9, 1),
        "allow_payments": True,
        "receiving_started": False,
        "created_by": s.U1.id,
        "order_type": None if E is None else "expense_order",
        "order_id": None if E is None else E.id,
        "description": None,
        "notes": None,
        "due_date": None,
        "invoice_number": None,
        "vendor_invoice_number": None,
        "payment_locked_reason": None,
        "void_note": None,
    }
    if confirmed:
        fields.update(invoice_status="confirmed", invoice_amount=Decimal("100.00"))
    if voided_inv:
        fields.update(invoice_status="voided", void_note="dup")
    fields.update(but)
    V = _add(db, AccountInvoice(**fields))
    if linked:
        link(db, E, V)
    return V


# Convention "linked" / "E.invoice_id = V.id, then db.flush()"
def link(db, E, V):
    E.invoice_id = V.id
    db.flush()


# Convention "invl(V, k, s)"
def invl(db, s, V, k, amount):
    return _add(
        db,
        InvoiceItem(
            workspace_id=V.workspace_id,
            invoice_id=V.id,
            line_number=k,
            description="Old line",
            quantity=Decimal("1"),
            unit_price=Decimal(amount),
            line_subtotal=Decimal(amount),
            created_by=s.U1.id,
        ),
    )


# Convention "pay(V, a)" (voided=True -> "voided pay")
def pay(db, s, V, amount, voided=False):
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "payment_amount": Decimal(amount),
        "payment_date": date(2026, 9, 1),
        "is_voided": False,
        "created_by": s.U1.id,
    }
    if voided:
        fields.update(
            is_voided=True, voided_at=T0, voided_by=s.U1.id, void_note="manual void"
        )
    return _add(db, InvoicePayment(**fields))


# Convention "ev(E, t)"
def ev(db, s, E, t):
    return _add(
        db,
        ExpenseOrderEvent(
            workspace_id=E.workspace_id,
            expense_order_id=E.id,
            event_type="note",
            description="n",
            performed_by=s.U1.id,
            created_at=t,
        ),
    )


# Convention "tpl" (waiving -> auto_approve True)
def tpl(db, s, waiving=False, **but):
    fields = {
        "workspace_id": s.W1.id,
        "template_name": "Monthly rent",
        "description": "Rent for the plant",
        "expense_category": "other",
        "cost_center_id": None,
        "account_id": s.A1.id,
        "is_active": True,
        "requires_approval": True,
        "auto_approve": False,
        "default_approver_id": None,
    }
    if waiving:
        fields["auto_approve"] = True
    fields.update(but)
    return _add(db, OrderTemplate(**fields))


# Convention "tplline(T, k, s)"
def tplline(db, T, k, amount):
    return _add(
        db,
        OrderTemplateItem(
            workspace_id=T.workspace_id,
            order_template_id=T.id,
            line_number=k,
            description="Rent",
            quantity=Decimal("1"),
            unit=None,
            unit_price=Decimal(amount),
            notes=None,
        ),
    )


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

_COUNT_TABLES = (
    "expense_orders",
    "expense_order_items",
    "expense_order_approvers",
    "expense_order_events",
    "account_invoices",
    "invoice_items",
    "invoice_events",
    "invoice_payments",
    "notifications",
    "workspace_audit_logs",
)


# Named check "nothing written": row counts of the listed tables (all workspaces)
def counts(db):
    return tuple(
        db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES
    )


# Convention "commit point": the test commits; the "nothing written" snapshot is taken here
def commit_point(db):
    db.commit()
    return counts(db)


# Convention "X": a pending workspace, flushed, not committed; returns X_ID
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Named check "unchanged(R)": every column of R, read straight from the database
def snap(db, R):
    table = type(R).__table__
    rid = R.id
    db.expire_all()
    row = db.execute(select(table).where(table.c.id == rid)).mappings().one_or_none()
    return None if row is None else dict(row)


# Named check "re-read R"
def reread(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


# Named check "gone(R)"
def gone(db, model, rid):
    db.expire_all()
    return db.get(model, rid) is None


# Named check "x_gone"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


# count of rows of `model` matching the filters, fresh query
def count_where(db, model, *where):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


# rows of `model` matching the filters, by id, fresh query
def rows_where(db, model, *where):
    db.expire_all()
    return list(db.scalars(select(model).where(*where).order_by(model.id)))


# Named check "EV(E)": E's expense_order_events by id
def EV(db, eid):
    db.expire_all()
    return list(
        db.scalars(
            select(ExpenseOrderEvent)
            .where(ExpenseOrderEvent.expense_order_id == eid)
            .order_by(ExpenseOrderEvent.id)
        )
    )


# Named check "types(E)"
def types(db, eid):
    return [e.event_type for e in EV(db, eid)]


# Named check "itypes(V)"
def itypes(db, vid):
    db.expire_all()
    return [
        e.event_type
        for e in db.scalars(
            select(InvoiceEvent)
            .where(InvoiceEvent.invoice_id == vid)
            .order_by(InvoiceEvent.id)
        )
    ]


# Named check "LINES(V)"
def LINES(db, vid):
    db.expire_all()
    return list(
        db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == vid)
            .order_by(InvoiceItem.line_number)
        )
    )


# Named check "notes()"
def notes(db):
    db.expire_all()
    return list(db.scalars(select(Notification).order_by(Notification.id)))


# Named check "recips()"
def recips(db):
    return sorted(n.recipient_user_id for n in notes(db))


# Named check "session clean"
def session_clean(db):
    return not db.new and not db.dirty and not db.deleted


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint(
        {c.key for c in inspect(type(r)).column_attrs}
    )


# the approver row of user U on order E, fresh query
def approver_of(db, eid, uid):
    db.expire_all()
    return db.scalars(
        select(ExpenseOrderApprover).where(
            ExpenseOrderApprover.expense_order_id == eid,
            ExpenseOrderApprover.user_id == uid,
        )
    ).one()


# Convention "spies"
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield cm, rb


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with patch.object(db, "commit", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


# Convention "failing refresh": the rollback spy is yielded
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


@contextmanager
def _failing_target(db, target):
    with patch(target, side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


# Convention "failing notify"
def failing_notify(db):
    return _failing_target(db, "app.services.expense_order_service.notify_invoice_action")


# Convention "failing section notify"
def failing_section_notify(db):
    return _failing_target(
        db, "app.services.expense_order_service.notify_section_confirm_needed"
    )


# Convention "failing approver notify"
def failing_approver_notify(db):
    return _failing_target(db, "app.services.expense_order_service.handle_add_approver")


_FROM = re.compile(
    r"\bFROM\b(.*?)(?:\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bFOR UPDATE\b|$)",
    re.DOTALL,
)


def _from_part(sql):
    m = _FROM.search(sql)
    return None if m is None else m.group(1)


def _from_names(sql, table):
    part = _from_part(sql)
    return part is not None and re.search(rf"\b{re.escape(table)}\b", part) is not None


# Convention "Statement recorder": every SQL statement sent during the When
class Recorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "after_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "after_cursor_execute", self._record)
        return False

    def _selects(self):
        return [
            (i, st)
            for i, st in enumerate(self.statements)
            if st.lstrip().upper().startswith("SELECT")
        ]

    def _first_read(self, table):
        for _, st in self._selects():
            if _from_names(st, table):
                return st
        return None

    def first_read_lock(self, table):
        """first-read lock(T): the first SELECT from T has FOR UPDATE, no SKIP LOCKED / NOWAIT."""
        st = self._first_read(table)
        return (
            st is not None
            and "FOR UPDATE" in st
            and "SKIP LOCKED" not in st
            and "NOWAIT" not in st
        )

    def lock_clause(self, table):
        """lock clause(T): that SELECT reads only T (no JOIN) and ends FOR UPDATE [OF T]."""
        st = self._first_read(table)
        if st is None:
            return False
        part = _from_part(st)
        one_table = part.strip() == table and "JOIN" not in st.upper()
        return one_table and re.search(rf"FOR UPDATE( OF {table})?\s*$", st) is not None

    def locks_before(self, table, other):
        """locks T before U: a FOR UPDATE SELECT on T precedes the first SELECT on U."""
        sel = self._selects()
        locks = [i for i, st in sel if _from_names(st, table) and "FOR UPDATE" in st]
        firsts = [i for i, st in sel if _from_names(st, other)]
        return bool(locks) and (not firsts or locks[0] < firsts[0])


# --------------------------------------------------------------------------- #
# create_expense_order
# --------------------------------------------------------------------------- #


def test_eos_e_01__new_order_committed_no_invoice_no_notice(db, s):
    """EOS-E-01 — a new order is committed and returned re-read; no invoice, no notification.
    Rules: create_expense_order E1, E2, E3; TC1, TC2."""
    commit_point(db)

    result = svc.create_expense_order(
        db,
        eo_in=ExpenseOrderCreate(
            expense_category="other", account_id=s.A1.id, description="March rent"
        ),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, ExpenseOrder)
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, ExpenseOrder, rid)
    assert row.workspace_id == s.W1.id
    assert row.account_id == s.A1.id
    assert row.description == "March rent"
    assert row.created_by == s.U2.id
    assert row.invoice_id is None
    # Then 4
    apprs = rows_where(db, ExpenseOrderApprover, ExpenseOrderApprover.expense_order_id == rid)
    assert len(apprs) == 1
    assert apprs[0].user_id == s.U2.id
    assert apprs[0].approved is False
    # Then 5
    assert (
        count_where(
            db,
            AccountInvoice,
            AccountInvoice.order_type == "expense_order",
            AccountInvoice.order_id == rid,
        )
        == 0
    )
    # Then 6
    assert notes(db) == []


def test_eos_e_02__manager_400_passes_extra_row_gone(db, s):
    """EOS-E-02 — the manager's 400 passes unchanged and the uncommitted extra row is gone.
    Rules: create_expense_order E1; TC3."""
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_expense_order(
                db,
                eo_in=ExpenseOrderCreate(
                    expense_category="other", account_id=s.A1.id, description="   "
                ),
                workspace_id=s.W1.id,
                user_id=s.U2.id,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Description is required"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_e_03__failing_commit_rolled_back(db, s):
    """EOS-E-03 — a failing commit is rolled back and re-raised; no order saved.
    Rules: create_expense_order E1; TC4."""
    before = commit_point(db)
    w1_id = s.W1.id
    data = ExpenseOrderCreate(
        expense_category="other", account_id=s.A1.id, description="March rent"
    )

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_expense_order(db, eo_in=data, workspace_id=w1_id, user_id=s.U2.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, ExpenseOrder, ExpenseOrder.workspace_id == w1_id) == 0
    # Then 4
    assert counts(db) == before


def test_eos_e_04__failing_refresh_keeps_order(db, s):
    """EOS-E-04 — a failing re-read after the commit leaves the order saved.
    Rules: create_expense_order E1; TC5."""
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    data = ExpenseOrderCreate(
        expense_category="other", account_id=s.A1.id, description="March rent"
    )

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_expense_order(db, eo_in=data, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = rows_where(db, ExpenseOrder, ExpenseOrder.workspace_id == w1_id)
    assert len(rows) == 1
    # Then 3
    assert rows[0].description == "March rent"
    assert rows[0].created_by == u2_id


# --------------------------------------------------------------------------- #
# update_expense_order
# --------------------------------------------------------------------------- #


def test_eos_u_01__edit_committed_no_notice(db, s):
    """EOS-U-01 — an edit without recorded approvals is committed; no notification.
    Rules: update_expense_order U1, U2 (no wipe -> no notice); TC1, TC2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    commit_point(db)
    eid = E.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(description="New rent"),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == eid
    db.rollback()
    # Then 3
    assert reread(db, ExpenseOrder, eid).description == "New rent"
    # Then 4
    assert notes(db) == []
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == eid) == 0


def test_eos_u_02__wipe_tells_creator_once(db, s):
    """EOS-U-02 — an edit that wipes approvals tells the creator once, not the approvers.
    Rules: update_expense_order U2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U4, approved=True)
    commit_point(db)
    eid = E.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(description="New rent"),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert len(notes(db)) == 1
    # Then 3
    assert notes(db)[0].recipient_user_id == s.U1.id
    assert notes(db)[0].notification_type == "section_confirm"
    # Then 4
    assert notes(db)[0].entity_type == "expense_order"
    assert notes(db)[0].entity_id == eid
    # Then 5
    assert notes(db)[0].preview == RESETMSG
    # Then 6
    assert approver_of(db, eid, s.U3.id).approved is False


def test_eos_u_03__creator_told_when_creator_edits(db, s):
    """EOS-U-03 — the creator is told also when the creator made the edit.
    Rules: update_expense_order U2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid = E.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(description="New rent"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id]
    # Then 3
    assert notes(db)[0].notification_type == "section_confirm"
    assert notes(db)[0].preview == RESETMSG


def test_eos_u_04__inactive_creator_no_notice(db, s):
    """EOS-U-04 — an inactive creator gets no notice when approvals are wiped.
    Rules: update_expense_order U2."""
    E = eo(db, s, "1", created_by=s.U5.id)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid = E.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(description="New rent"),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert approver_of(db, eid, s.U3.id).approved is False
    # Then 3
    assert notes(db) == []


def test_eos_u_05__linked_draft_brought_in_step(db, s):
    """EOS-U-05 — a linked draft is brought in step and stays linked.
    Rules: update_expense_order U3; _sync_or_create_invoice Y2; Q4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    line(db, E, 2, "50.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "999.00")
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(description="New rent"),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).invoice_id == vid
    # Then 3
    assert [l.line_subtotal for l in LINES(db, vid)] == [
        Decimal("100.00"),
        Decimal("50.00"),
    ]
    # Then 4
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("150.00")
    assert v.notes == "New rent"
    # Then 5
    assert "items_synced" in itypes(db, vid)


def test_eos_u_06__required_zero_drafts_invoice_and_notice(db, s):
    """EOS-U-06 — lowering required approvals to 0 drafts the invoice and sends the draft notice.
    Rules: update_expense_order U3; _sync_or_create_invoice Y7."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    commit_point(db)
    eid = E.id

    result = svc.update_expense_order(
        db,
        eo_id=eid,
        eo_in=ExpenseOrderUpdate(required_approvals=0),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is not None
    inv_id = e.invoice_id
    # Then 3
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_type == "payable"
    assert v.account_id == s.A1.id
    assert v.order_id == eid
    assert v.invoice_amount == Decimal("100.00")
    # Then 4
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 5
    for n in notes(db):
        assert n.notification_type == "invoice_action"
        assert n.preview == DRAFTP
        assert n.source_id == inv_id


@xfail(629)
def test_eos_u_07__new_account_refused_undoes_edit(db, s):
    """EOS-U-07 — the invoice manager refusing the new account undoes the whole edit.
    Rules: update_expense_order U4; _resync_draft_invoice R4b [BUG-629]; TC3."""
    A3 = acct(db, s, "No Bills", allow_invoices=False)
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_expense_order(
            db,
            eo_id=E.id,
            eo_in=ExpenseOrderUpdate(account_id=A3.id, description="New rent"),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, V) == sV
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_u_08__missing_order_404(db, s):
    """EOS-U-08 — a missing order: the manager's 404 passes unchanged and the extra row is gone.
    Rules: update_expense_order U1; TC3."""
    E = eo(db, s, "1")
    commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_expense_order(
                db,
                eo_id=MISSING,
                eo_in=ExpenseOrderUpdate(description="New rent"),
                workspace_id=s.W1.id,
                user_id=s.U2.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, E) == sE
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_u_09__w2_order_404(db, s):
    """EOS-U-09 — another workspace's order (W2) gets the 404, nothing changed.
    Rules: update_expense_order U1; HR-16."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2")
    commit_point(db)
    sZ = snap(db, Z)
    zid = Z.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_expense_order(
            db,
            eo_id=zid,
            eo_in=ExpenseOrderUpdate(description="New rent"),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 4
    assert snap(db, Z) == sZ


def test_eos_u_10__failing_commit_keeps_old_values(db, s):
    """EOS-U-10 — a failing commit keeps the old description and the old invoice lines.
    Rules: update_expense_order U1; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    OL = invl(db, s, V, 1, "999.00")
    before = commit_point(db)
    sOL = snap(db, OL)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_expense_order(
                db,
                eo_id=eid,
                eo_in=ExpenseOrderUpdate(description="New rent"),
                workspace_id=s.W1.id,
                user_id=s.U2.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, ExpenseOrder, eid).description == "Office rent"
    # Then 4
    assert snap(db, OL) == sOL
    # Then 5
    assert counts(db) == before


@xfail(3068)
def test_eos_u_11__clearing_account_with_draft_refused(db, s):
    """EOS-U-11 — clearing the account while a draft invoice is linked is refused.
    Rules: _resync_draft_invoice R5a [BUG-3068]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_expense_order(
            db,
            eo_id=E.id,
            eo_in=ExpenseOrderUpdate(account_id=None),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == CLEARACC
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


@xfail(3068)
def test_eos_u_12__clearing_account_with_confirmed_refused(db, s):
    """EOS-U-12 — clearing the account while a confirmed invoice is linked is refused too.
    Rules: _resync_draft_invoice R5a [BUG-3068]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    inv(db, s, E, confirmed=True, linked=True)
    commit_point(db)
    sE = snap(db, E)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_expense_order(
            db,
            eo_id=E.id,
            eo_in=ExpenseOrderUpdate(account_id=None),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == CLEARACC
    # Then 4
    assert snap(db, E) == sE


def test_eos_u_13__failing_section_notice_undoes_edit(db, s):
    """EOS-U-13 — a failing approvals-reset notice undoes the whole edit.
    Rules: update_expense_order U2; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    before = commit_point(db)
    sE, sP3 = snap(db, E), snap(db, P3)
    x, x_id = mk_x(db)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_section_notify(db) as rb:
            svc.update_expense_order(
                db,
                eo_id=eid,
                eo_in=ExpenseOrderUpdate(description="New rent"),
                workspace_id=s.W1.id,
                user_id=s.U2.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert x not in db
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert snap(db, P3) == sP3
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_u_14__deleted_new_account_refused_undoes_edit(db, s):
    """EOS-U-14 — a deleted new account is refused and the whole edit is undone (today and after the fix).
    Rules: update_expense_order U4; _resync_draft_invoice R4, R4a; TC3."""
    AD = acct(db, s, "Old Vendor", is_deleted=True)
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_expense_order(
            db,
            eo_id=E.id,
            eo_in=ExpenseOrderUpdate(account_id=AD.id, description="New rent"),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign invoice to deleted account"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, V) == sV
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


# --------------------------------------------------------------------------- #
# get_expense_order
# --------------------------------------------------------------------------- #


def test_eos_g_01__returns_order_no_commit_no_rollback(db, s):
    """EOS-G-01 — returns the order; neither commits nor rolls back; a pending row stays pending.
    Rules: get_expense_order G1; TC6."""
    E = eo(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_expense_order(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, ExpenseOrder)
    assert result.id == E.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_eos_g_02__voided_order_returned(db, s):
    """EOS-G-02 — a voided order is returned.
    Rules: get_expense_order G1."""
    E = eo(db, s, "1", voided=True)
    commit_point(db)

    result = svc.get_expense_order(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == E.id
    assert result.voided is True


def test_eos_g_03__completed_order_returned(db, s):
    """EOS-G-03 — a completed order is returned.
    Rules: get_expense_order G1."""
    E = eo(db, s, "1", completed=True)
    inv(db, s, E, confirmed=True, linked=True)
    commit_point(db)

    result = svc.get_expense_order(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == E.id
    assert result.completed_at == T0


def test_eos_g_04__w0_order_404(db, s):
    """EOS-G-04 — a W0 order (lower workspace id) gets the 404.
    Rules: get_expense_order G1."""
    Z = eo(db, s, "0", ws="0")
    eo(db, s, "1")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_expense_order(db, eo_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {Z.id} not found"


def test_eos_g_05__w2_order_404(db, s):
    """EOS-G-05 — a W2 order (higher workspace id) gets the 404.
    Rules: get_expense_order G1."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_expense_order(db, eo_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {Z.id} not found"


def test_eos_g_06__404_no_rollback_pending_row_kept(db, s):
    """EOS-G-06 — a 404 neither rolls back nor drops a pending row.
    Rules: get_expense_order G1; TC6."""
    eo(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_expense_order(db, eo_id=MISSING, workspace_id=s.W1.id)

    # Then 1
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# list_expense_orders
# --------------------------------------------------------------------------- #


def test_eos_l_01__page_of_workspace_orders(db, s):
    """EOS-L-01 — returns the page of the workspace's orders; W0 and W2 orders never appear.
    Rules: list_expense_orders L-1."""
    eo(db, s, "0", ws="0")
    A = eo(db, s, "1")
    B = eo(db, s, "2")
    C = eo(db, s, "3")
    eo(db, s, "9", ws="2")
    commit_point(db)

    result = svc.list_expense_orders(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, ExpenseOrderListResponse)
    # Then 2
    assert result.total == 3
    assert result.skip == 0
    assert result.has_more is False
    # Then 3
    assert {o.id for o in result.items} == {A.id, B.id, C.id}


def test_eos_l_02__default_limit_100(db, s):
    """EOS-L-02 — with no limit given, 101 orders give 100 and `has_more` true.
    Rules: list_expense_orders L-1 (own default limit 100)."""
    eo_many(db, s, 101)
    commit_point(db)

    result = svc.list_expense_orders(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.items) == 100
    # Then 2
    assert result.limit == 100
    assert result.total == 101
    assert result.has_more is True


def test_eos_l_03__skip_and_limit_passed_on(db, s):
    """EOS-L-03 — skip and limit=1000 are passed on.
    Rules: list_expense_orders L-1."""
    A = eo(db, s, "1")
    B = eo(db, s, "2")
    C = eo(db, s, "3")
    commit_point(db)

    result = svc.list_expense_orders(db, workspace_id=s.W1.id, skip=1, limit=1000)

    # Then 1
    assert len(result.items) == 2
    assert {o.id for o in result.items} <= {A.id, B.id, C.id}
    # Then 2
    assert result.skip == 1
    assert result.limit == 1000
    assert result.total == 3


def test_eos_l_04__hub_filter_by_keyword(db, s):
    """EOS-L-04 — a hub filter passed by keyword reaches the page.
    Rules: list_expense_orders L-1."""
    A = eo(db, s, "1")
    eo(db, s, "2", voided=True)
    commit_point(db)

    result = svc.list_expense_orders(db, workspace_id=s.W1.id, exclude_voided=True)

    # Then 1
    assert [o.id for o in result.items] == [A.id]
    # Then 2
    assert result.total == 1


def test_eos_l_05__unknown_filter_type_error(db, s):
    """EOS-L-05 — an unknown keyword filter raises TypeError.
    Rules: list_expense_orders L-2."""
    eo(db, s, "1")
    commit_point(db)

    # Then 1
    with pytest.raises(TypeError):
        svc.list_expense_orders(db, workspace_id=s.W1.id, colour="red")


def test_eos_l_06__list_no_commit_no_rollback(db, s):
    """EOS-L-06 — the list neither commits nor rolls back.
    Rules: list_expense_orders L-1; TC6."""
    eo(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_expense_orders(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# _hub_filter_kwargs
# --------------------------------------------------------------------------- #


def test_eos_k_01__defaults(db, s):
    """EOS-K-01 — with no arguments, the ten keys with their defaults.
    Rules: _hub_filter_kwargs Returns, K1, K2."""
    result = svc._hub_filter_kwargs()

    # Then 1
    assert result == {
        "expense_category": None,
        "account_id": None,
        "invoice_id": None,
        "date_from": None,
        "date_to": None,
        "status_ids": None,
        "invoice_filter": None,
        "search": None,
        "exclude_complete": False,
        "exclude_voided": False,
    }


def test_eos_k_02__values_passed_through(db, s):
    """EOS-K-02 — every value is passed through unchanged; "linked" stays as given.
    Rules: _hub_filter_kwargs K1, K2."""
    result = svc._hub_filter_kwargs(
        expense_category="factory",
        account_id=7,
        invoice_id=8,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        status_ids=[3, 4],
        invoice_filter="linked",
        search="rent",
        exclude_complete=True,
        exclude_voided=True,
    )

    # Then 1
    assert result == {
        "expense_category": "factory",
        "account_id": 7,
        "invoice_id": 8,
        "date_from": date(2026, 9, 1),
        "date_to": date(2026, 9, 30),
        "status_ids": [3, 4],
        "invoice_filter": "linked",
        "search": "rent",
        "exclude_complete": True,
        "exclude_voided": True,
    }


@pytest.mark.parametrize(
    "given",
    [
        pytest.param("", id="EOS-K-03"),
        pytest.param("all", id="EOS-K-04"),
    ],
)
def test_eos_k_03_04__empty_or_all_becomes_none(db, s, given):
    """EOS-K-03 / EOS-K-04 — `invoice_filter=""` / `"all"` becomes None.
    Rules: _hub_filter_kwargs K2."""
    result = svc._hub_filter_kwargs(invoice_filter=given)

    # Then 1
    assert result["invoice_filter"] is None


@pytest.mark.parametrize(
    "given",
    [
        pytest.param("All", id="EOS-K-05"),
        pytest.param(" all", id="EOS-K-06"),
        pytest.param("invoiced", id="EOS-K-07"),
    ],
)
def test_eos_k_05_07__other_values_passed_as_given(db, s, given):
    """EOS-K-05 / K-06 / K-07 — `"All"`, `" all"`, `"invoiced"` are passed as given.
    Rules: _hub_filter_kwargs K2."""
    result = svc._hub_filter_kwargs(invoice_filter=given)

    # Then 1
    assert result["invoice_filter"] == given


# --------------------------------------------------------------------------- #
# list_expense_orders_page
# --------------------------------------------------------------------------- #


def test_eos_p_01__same_filters_defaults_echoed(db, s):
    """EOS-P-01 — total and items come from the same filters; defaults skip 0 / limit 50 are echoed.
    Rules: list_expense_orders_page P-1, P-2."""
    eo(db, s, "0", ws="0")
    A = eo(db, s, "1")
    B = eo(db, s, "2")
    eo(db, s, "3", voided=True)
    eo(db, s, "9", ws="2")
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id, exclude_voided=True)

    # Then 1
    assert isinstance(result, ExpenseOrderListResponse)
    # Then 2
    assert result.total == 2
    # Then 3
    assert {o.id for o in result.items} == {A.id, B.id}
    # Then 4
    assert result.skip == 0
    assert result.limit == 50
    assert result.has_more is False


def test_eos_p_02__default_limit_50(db, s):
    """EOS-P-02 — with no limit given, 51 orders give 50 and `has_more` true.
    Rules: list_expense_orders_page P-1, P-3 (default limit 50)."""
    eo_many(db, s, 51)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.items) == 50
    # Then 2
    assert result.total == 51
    assert result.has_more is True


def test_eos_p_03__short_of_total_has_more(db, s):
    """EOS-P-03 — skip + items short of total: `has_more` true.
    Rules: list_expense_orders_page P-3."""
    eo_many(db, s, 5)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id, skip=0, limit=4)

    # Then 1
    assert len(result.items) == 4
    # Then 2
    assert result.total == 5
    assert result.skip == 0
    assert result.limit == 4
    assert result.has_more is True


def test_eos_p_04__equal_to_total_no_more(db, s):
    """EOS-P-04 — skip + items equal to total: `has_more` false.
    Rules: list_expense_orders_page P-3."""
    eo_many(db, s, 5)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id, skip=1, limit=4)

    # Then 1
    assert len(result.items) == 4
    # Then 2
    assert result.total == 5
    assert result.skip == 1
    assert result.has_more is False


def test_eos_p_05__skip_beyond_total(db, s):
    """EOS-P-05 — skip beyond the total: no items, `has_more` false.
    Rules: list_expense_orders_page P-3."""
    eo_many(db, s, 5)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id, skip=7, limit=1000)

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 5
    assert result.skip == 7
    assert result.limit == 1000
    assert result.has_more is False


def test_eos_p_06__no_match(db, s):
    """EOS-P-06 — no match: total 0, no items, `has_more` false.
    Rules: list_expense_orders_page P-3."""
    eo(db, s, "9", ws="2")
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 0
    assert result.has_more is False


def test_eos_p_07__invoice_filter_all_lists_both(db, s):
    """EOS-P-07 — `invoice_filter="all"` lists linked and unlinked orders alike.
    Rules: list_expense_orders_page P-1; _hub_filter_kwargs K2."""
    A = eo(db, s, "1")
    B = eo(db, s, "2")
    inv(db, s, B, linked=True)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id, invoice_filter="all")

    # Then 1
    assert result.total == 2
    # Then 2
    assert {o.id for o in result.items} == {A.id, B.id}


def test_eos_p_08__page_no_commit_no_rollback(db, s):
    """EOS-P-08 — the page neither commits nor rolls back.
    Rules: list_expense_orders_page P-4; TC6."""
    eo(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_expense_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_eos_p_09__no_filter_lists_completed_and_voided(db, s):
    """EOS-P-09 — with no filter, completed and voided orders are listed.
    Rules: list_expense_orders_page P-1; _hub_filter_kwargs defaults (exclude_complete=False, exclude_voided=False)."""
    A = eo(db, s, "1")
    C = eo(db, s, "2", completed=True)
    D = eo(db, s, "3", voided=True)
    commit_point(db)

    result = svc.list_expense_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total == 3
    # Then 2
    assert {o.id for o in result.items} == {A.id, C.id, D.id}
    # Then 3
    assert result.has_more is False


# --------------------------------------------------------------------------- #
# get_expense_order_hub_stats
# --------------------------------------------------------------------------- #


def _five(r):
    return (r.total_count, r.total_value, r.open_count, r.open_value, r.not_invoiced_count)


def test_eos_h_01__five_figures_are_managers(db, s):
    """EOS-H-01 — the five figures are the manager's tuple, in order.
    Rules: get_expense_order_hub_stats H-1, H-2."""
    m100 = {"subtotal": Decimal("100.00"), "total_amount": Decimal("100.00")}
    eo(db, s, "1", **m100)
    B = eo(db, s, "2", subtotal=Decimal("200.00"), total_amount=Decimal("200.00"))
    inv(db, s, B, linked=True)
    C = eo(
        db, s, "3", completed=True, subtotal=Decimal("400.00"), total_amount=Decimal("400.00")
    )
    inv(db, s, C, confirmed=True, linked=True)
    eo(db, s, "9", ws="2", subtotal=Decimal("800.00"), total_amount=Decimal("800.00"))
    commit_point(db)

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert _five(result) == tuple(
        mgr.expense_order_hub_stats(db, s.W1.id, **svc._hub_filter_kwargs())
    )
    # Then 2
    assert _five(result) == (3, Decimal("700.00"), 2, Decimal("300.00"), 1)


def test_eos_h_02__one_filter_feeds_all(db, s):
    """EOS-H-02 — one filter feeds the figures and the recent list alike.
    Rules: get_expense_order_hub_stats H-1, H-3."""
    A = eo(db, s, "1", subtotal=Decimal("100.00"), total_amount=Decimal("100.00"))
    eo(db, s, "2", voided=True, subtotal=Decimal("900.00"), total_amount=Decimal("900.00"))
    commit_point(db)

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id, exclude_voided=True)

    # Then 1
    assert result.total_count == 1
    assert result.total_value == Decimal("100.00")
    # Then 2
    assert [x.id for x in result.recent_orders] == [A.id]


# [claude] EOS-H-03
def test_eos_h_03__recent_at_most_10_in_managers_order(db, s):
    """EOS-H-03 — `recent_orders` holds at most 10, in the manager's order.
    Rules: get_expense_order_hub_stats H-3."""
    for k in range(1, 12):
        eo(db, s, str(k))
    commit_point(db)
    rec = mgr.list_expense_orders_recent_for_hub(
        db, s.W1.id, limit=10, **svc._hub_filter_kwargs()
    )

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.recent_orders) == 10
    # Then 2
    assert [x.id for x in result.recent_orders] == [o.id for o in rec]
    # Then 3
    for i, o in enumerate(rec):
        assert result.recent_orders[i] == expense_order_to_recent_summary(o)


# [claude] EOS-H-04
def test_eos_h_04__snapshot_copies_buckets(db, s):
    """EOS-H-04 — the financial snapshot copies the manager's buckets without changing a number.
    Rules: get_expense_order_hub_stats H-4, H-4a."""
    eo(
        db,
        s,
        "1",
        subtotal=Decimal("100.00"),
        total_amount=Decimal("100.00"),
        due_date=date(2026, 9, 20),
    )
    B = eo(
        db,
        s,
        "2",
        expense_category="department",
        cost_center_id=s.DEP1.id,
        account_id=s.A2.id,
        subtotal=Decimal("250.00"),
        total_amount=Decimal("250.00"),
    )
    inv(
        db,
        s,
        B,
        confirmed=True,
        account_id=s.A2.id,
        invoice_amount=Decimal("250.00"),
        linked=True,
    )
    commit_point(db)
    snap_raw = mgr.expense_order_financial_snapshot(db, s.W1.id, **svc._hub_filter_kwargs())

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    fs = result.financial_snapshot

    def samples(rows):
        return [(x["id"], x["order_number"], x["total_value"], x["sublabel"]) for x in rows]

    def osamples(rows):
        return [(x.id, x.order_number, x.total_value, x.sublabel) for x in rows]

    # Then 1
    for name in ("category_breakdown", "stage_pipeline"):
        assert [(b.key, b.label, b.count, b.total_value) for b in getattr(fs, name)] == [
            (r["key"], r["label"], r["count"], r["total_value"]) for r in snap_raw[name]
        ]
    # Then 2
    assert [(b.account_id, b.account_name, b.count, b.total_value) for b in fs.open_by_account] == [
        (r["account_id"], r["account_name"], r["count"], r["total_value"])
        for r in snap_raw["open_by_account"]
    ]
    # Then 3
    assert [(b.key, b.label, b.count, b.total_value) for b in fs.due_timeline] == [
        (r["key"], r["label"], r["count"], r["total_value"]) for r in snap_raw["due_timeline"]
    ]
    assert [osamples(b.samples) for b in fs.due_timeline] == [
        samples(r["samples"]) for r in snap_raw["due_timeline"]
    ]
    # Then 4
    assert [(b.key, b.label, b.count, b.outstanding_value) for b in fs.unpaid_pipeline] == [
        (r["key"], r["label"], r["count"], r["outstanding_value"])
        for r in snap_raw["unpaid_pipeline"]
    ]
    assert [osamples(b.samples) for b in fs.unpaid_pipeline] == [
        samples(r["samples"]) for r in snap_raw["unpaid_pipeline"]
    ]


def test_eos_h_05__empty_workspace(db, s):
    """EOS-H-05 — an empty workspace: empty lists stay empty, zero figures.
    Rules: get_expense_order_hub_stats H-2, H-3, H-4."""
    eo(db, s, "9", ws="2")
    commit_point(db)

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total_count == 0
    assert result.open_count == 0
    assert result.not_invoiced_count == 0
    # Then 2
    assert result.recent_orders == []
    # Then 3
    assert result.financial_snapshot.category_breakdown == []
    assert result.financial_snapshot.open_by_account == []


def test_eos_h_06__stats_no_commit_no_rollback(db, s):
    """EOS-H-06 — the stats neither commit nor roll back.
    Rules: get_expense_order_hub_stats H-5; TC6."""
    eo(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total_count == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_eos_h_07__response_class_and_summary_fields(db, s):
    """EOS-H-07 — the response class and every recent-summary field.
    Rules: get_expense_order_hub_stats Returns, H-3, H-3a."""
    A = eo(
        db,
        s,
        "1",
        due_date=date(2026, 10, 15),
        subtotal=Decimal("100.00"),
        total_amount=Decimal("100.00"),
    )
    VA = inv(db, s, A, linked=True)
    commit_point(db)

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, ExpenseOrderHubStatsResponse)
    # Then 2
    assert len(result.recent_orders) == 1
    sm = result.recent_orders[0]
    assert isinstance(sm, OrderHubRecentSummary)
    # Then 3
    assert sm.id == A.id
    assert sm.order_number == A.expense_number
    assert sm.status_id == 0
    assert sm.status_name is None
    # Then 4
    assert sm.account_id == s.A1.id
    assert sm.invoice_id == VA.id
    assert sm.total_amount == Decimal("100.00")
    assert sm.expense_category == "other"
    # Then 5
    assert sm.expense_date == date(2026, 9, 1)
    assert sm.due_date == date(2026, 10, 15)
    assert sm.created_at == A.created_at
    assert sm.updated_at == A.updated_at
    # Then 6
    assert sm.source_location_type is None
    assert sm.destination_location_type is None


def test_eos_h_08__no_filter_counts_voided_order(db, s):
    """EOS-H-08 — with no filter, a voided order is counted.
    Rules: get_expense_order_hub_stats H-1, H-2; _hub_filter_kwargs defaults (exclude_complete=False, exclude_voided=False)."""
    A = eo(db, s, "1", subtotal=Decimal("100.00"), total_amount=Decimal("100.00"))
    D = eo(db, s, "2", voided=True, subtotal=Decimal("200.00"), total_amount=Decimal("200.00"))
    commit_point(db)

    result = svc.get_expense_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    figs = (
        result.total_count,
        result.total_value,
        result.open_count,
        result.open_value,
        result.not_invoiced_count,
    )
    assert figs == tuple(mgr.expense_order_hub_stats(db, s.W1.id, **svc._hub_filter_kwargs()))
    # Then 2
    assert figs != tuple(
        mgr.expense_order_hub_stats(db, s.W1.id, **svc._hub_filter_kwargs(exclude_voided=True))
    )
    # Then 3
    assert result.total_count == 2
    # Then 4
    assert {r.id for r in result.recent_orders} == {A.id, D.id}


# --------------------------------------------------------------------------- #
# delete_expense_order
# --------------------------------------------------------------------------- #


def test_eos_x_01__deleted_and_committed(db, s):
    """EOS-X-01 — an order without an invoice is deleted and committed; no notification.
    Rules: delete_expense_order X1, X3; Returns; TC1."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    commit_point(db)
    eid, l1_id = E.id, L1.id

    result = svc.delete_expense_order(db, eo_id=eid, workspace_id=s.W1.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert gone(db, ExpenseOrder, eid)
    # Then 3
    assert gone(db, ExpenseOrderItem, l1_id)
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0
    # Then 5
    assert notes(db) == []


@xfail(1193)
def test_eos_x_02__deleter_named_in_audit_row(db, s):
    """EOS-X-02 — the deleter is passed on and named in the audit row.
    Rules: delete_expense_order X2 [BUG-1193]."""
    E = eo(db, s, "1")
    eid = E.id
    commit_point(db)

    # Then 1 (the call itself raises TypeError today: no `user_id` parameter)
    result = svc.delete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)
    assert result is None
    db.rollback()
    # Then 2
    assert gone(db, ExpenseOrder, eid)
    # Then 3
    logs = rows_where(
        db,
        WorkspaceAuditLog,
        WorkspaceAuditLog.resource_type == "expense_order",
        WorkspaceAuditLog.resource_id == eid,
    )
    assert len(logs) == 1
    # Then 4
    assert logs[0].user_id == s.U2.id
    assert logs[0].action == "expense_order_deleted"
    assert logs[0].workspace_id == s.W1.id


def test_eos_x_03__missing_order_404(db, s):
    """EOS-X-03 — a missing order: 404 passes unchanged, the extra row is gone.
    Rules: delete_expense_order X1; TC3."""
    E = eo(db, s, "1")
    commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_expense_order(db, eo_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, E) == sE
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_x_04__completed_order_400(db, s):
    """EOS-X-04 — a completed order: 400 passes unchanged, nothing deleted.
    Rules: delete_expense_order X1; TC3."""
    E = eo(db, s, "1", completed=True)
    V = inv(db, s, E, confirmed=True, linked=True)
    commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a completed expense order"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_x_05__w2_order_404(db, s):
    """EOS-X-05 — another workspace's order (W2): 404, nothing deleted.
    Rules: delete_expense_order X1; HR-16."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2")
    commit_point(db)
    sZ = snap(db, Z)
    zid = Z.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_expense_order(db, eo_id=zid, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 4
    assert snap(db, Z) == sZ


@xfail(742)
def test_eos_x_06__linked_draft_refused_void_instead(db, s):
    """EOS-X-06 — an order with a linked draft is refused: void it instead.
    Rules: delete_expense_order X1 [BUG-742] (manager pass-through)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)
    eid = E.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_expense_order(db, eo_id=eid, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Void the expense order instead"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_x_07__failing_commit_keeps_order(db, s):
    """EOS-X-07 — a failing commit keeps the order.
    Rules: delete_expense_order X1; TC4."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    commit_point(db)
    sE, sL1 = snap(db, E), snap(db, L1)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_expense_order(db, eo_id=eid, workspace_id=s.W1.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert snap(db, L1) == sL1


# --------------------------------------------------------------------------- #
# complete_expense_order
# --------------------------------------------------------------------------- #


def _met_with_draft(db, s, amounts=("100.00",)):
    """E = eo "1"; its lines; appr(E, U3) approved; V = inv(E) linked; V's lines."""
    E = eo(db, s, "1")
    for k, a in enumerate(amounts, 1):
        line(db, E, k, a)
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    for k, a in enumerate(amounts, 1):
        invl(db, s, V, k, a)
    return E, V


def test_eos_c_01__stamped_complete_and_committed(db, s):
    """EOS-C-01 — a met order with a draft: the order is stamped complete and committed.
    Rules: complete_expense_order C8, C10; TC1, TC2."""
    E, V = _met_with_draft(db, s)
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == eid
    db.rollback()
    # Then 3
    e = reread(db, ExpenseOrder, eid)
    assert e.completed_at == NOW
    assert e.completed_by == s.U2.id
    assert e.updated_by == s.U2.id
    assert e.voided is False
    assert e.invoice_id == vid
    # Then 4
    assert types(db, eid) == ["order_completed"]
    # Then 5
    evs = EV(db, eid)
    assert evs[0].description == "Invoice confirmed and expense order marked complete"
    assert evs[0].performed_by == s.U2.id
    assert evs[0].metadata_json is None


def test_eos_c_02__draft_confirmed_at_line_sum(db, s):
    """EOS-C-02 — a met order with a draft: the draft is confirmed at its line sum.
    Rules: complete_expense_order C8."""
    E, V = _met_with_draft(db, s, ("100.00", "25.50"))
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("125.50")
    # Then 3
    assert "confirmed" in itypes(db, vid)


def test_eos_c_03__confirmed_notice_recipients(db, s):
    """EOS-C-03 — the confirmed notice goes to every approver and the creator, active members only.
    Rules: complete_expense_order C8."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U5, approved=True)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 3
    for n in notes(db):
        assert n.notification_type == "invoice_action"
        assert n.entity_type == "expense_order"
        assert n.entity_id == eid
    # Then 4
    for n in notes(db):
        assert n.source_type == "invoice"
        assert n.source_id == vid
    # Then 5
    for n in notes(db):
        assert n.preview == f"confirmed|Invoice confirmed on EXP-{eid} — order locked"


def test_eos_c_04__already_completed_returned_as_is(db, s):
    """EOS-C-04 — an already completed order is returned as it is: no check, no write, no commit, no rollback.
    Rules: complete_expense_order C2."""
    E = eo(db, s, "1", completed=True)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, confirmed=True, linked=True)
    commit_point(db)
    sV = snap(db, V)
    eid = E.id
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.complete_expense_order(
            db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id
        )

    # Then 1
    assert result.id == eid
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    e = reread(db, ExpenseOrder, eid)
    assert e.completed_at == T0
    assert e.completed_by == s.U1.id
    assert e.updated_by == s.U1.id
    # Then 6
    assert snap(db, V) == sV
    # Then 7
    assert types(db, eid) == []
    # Then 8
    assert notes(db) == []


@xfail(3065)
def test_eos_c_05__voided_order_refused(db, s):
    """EOS-C-05 — a voided order is refused before anything else.
    Rules: complete_expense_order C3, Errors row 2 [BUG-3065]."""
    E = eo(db, s, "1", voided=True, waived=True)
    line(db, E, 1, "50.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "50.00")
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Expense order is voided"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, V) == sV
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


@xfail(3065)
def test_eos_c_06__voided_check_before_approvals(db, s):
    """EOS-C-06 — the voided check comes before the approvals check.
    Rules: complete_expense_order C3, C4 [BUG-3065]."""
    E = eo(db, s, "1", voided=True)
    line(db, E, 1, "50.00")
    appr(db, s, E, s.U3)
    commit_point(db)
    sE = snap(db, E)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Expense order is voided"
    # Then 3
    assert snap(db, E) == sE


def test_eos_c_07__voided_unmet_never_completed(db, s):
    """EOS-C-07 — a voided order with unmet approvals is never completed (today and after the fix).
    Rules: complete_expense_order C3, C4."""
    E = eo(db, s, "1", voided=True)
    line(db, E, 1, "50.00")
    appr(db, s, E, s.U3)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert x not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_c_08__approvals_not_met_400(db, s):
    """EOS-C-08 — approvals not met: 400, the draft stays a draft.
    Rules: complete_expense_order C4, Errors row 3; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U4)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTMET
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, V) == sV
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


@xfail(755)
def test_eos_c_09__no_approvers_counts_as_not_met(db, s):
    """EOS-C-09 — no approvers and no explicit requirement counts as not met.
    Rules: complete_expense_order C4 [BUG-755] (manager pass-through)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    sE, sV = snap(db, E), snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTMET
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert snap(db, V) == sV


def test_eos_c_10__waived_completes_creator_told(db, s):
    """EOS-C-10 — a waived order (required 0) with no approvers completes; only the creator is told.
    Rules: complete_expense_order C4, C8, C10."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "40.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "40.00")
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).completed_at == NOW
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("40.00")
    # Then 4
    assert recips(db) == [s.U1.id]


def test_eos_c_11__no_invoice_linked_400(db, s):
    """EOS-C-11 — no invoice linked: 400 with the "set an account" text.
    Rules: complete_expense_order C5, Errors row 4; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOINV
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_c_12__w2_invoice_not_found(db, s):
    """EOS-C-12 — the linked invoice is a W2 invoice: "Linked invoice not found", no id shown.
    Rules: complete_expense_order C6, Errors row 5; HR-16."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    Z = inv(db, s, E, ws="2", linked=True)
    invl(db, s, Z, 1, "100.00")
    before = commit_point(db)
    sE, sZ = snap(db, E), snap(db, Z)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Linked invoice not found"
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert snap(db, Z) == sZ
    # Then 6
    assert counts(db) == before


def test_eos_c_13__w0_invoice_not_found(db, s):
    """EOS-C-13 — the linked invoice is a W0 invoice: "Linked invoice not found".
    Rules: complete_expense_order C6; HR-16."""
    Z = inv(db, s, None, ws="0")
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    link(db, E, Z)
    commit_point(db)
    sE, sZ = snap(db, E), snap(db, Z)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Linked invoice not found"
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert snap(db, Z) == sZ


def test_eos_c_14__linked_invoice_voided_400(db, s):
    """EOS-C-14 — the linked invoice was voided: 400, nothing written.
    Rules: complete_expense_order C7, Errors row 6."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, voided_inv=True, linked=True)
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == VOIDINV
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


@xfail(628)
def test_eos_c_15__draft_without_lines_not_confirmed(db, s):
    """EOS-C-15 — a draft with no lines cannot be confirmed: 400, the order is not completed.
    Rules: complete_expense_order C8, Errors row 7 [BUG-628] (invoice manager pass-through)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Add at least one line item before confirming"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_c_16__already_confirmed_left_order_completed(db, s):
    """EOS-C-16 — an invoice already confirmed is left as it is; the order is still completed, nobody told.
    Rules: complete_expense_order C9, C10."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, confirmed=True, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    sV = snap(db, V)
    eid, vid = E.id, V.id

    result = svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert snap(db, V) == sV
    # Then 3
    assert itypes(db, vid) == []
    # Then 4
    e = reread(db, ExpenseOrder, eid)
    assert e.completed_at == NOW
    assert e.completed_by == s.U2.id
    assert e.updated_by == s.U2.id
    # Then 5
    assert types(db, eid) == ["order_completed"]
    assert EV(db, eid)[0].description == "Invoice confirmed and expense order marked complete"
    # Then 6
    assert notes(db) == []


def test_eos_c_17__missing_order_404(db, s):
    """EOS-C-17 — a missing order: 404, the extra row is gone.
    Rules: complete_expense_order C1, Errors row 1; TC3."""
    eo(db, s, "1")
    commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_eos_c_18__w2_order_404(db, s):
    """EOS-C-18 — another workspace's order (W2): 404, not completed.
    Rules: complete_expense_order C1; HR-16."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2", waived=True)
    line(db, Z, 1, "100.00")
    VZ = inv(db, s, Z, ws="2", linked=True)
    invl(db, s, VZ, 1, "100.00")
    commit_point(db)
    sZ, sVZ = snap(db, Z), snap(db, VZ)
    zid = Z.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=zid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 4
    assert snap(db, Z) == sZ
    # Then 5
    assert snap(db, VZ) == sVZ


# [claude] EOS-C-19
def test_eos_c_19__failing_notice_undoes_confirm(db, s):
    """EOS-C-19 — a failing notification undoes the confirm.
    Rules: complete_expense_order C8; TC3."""
    E, V = _met_with_draft(db, s)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)
    eid, vid = E.id, V.id

    with pytest.raises(RuntimeError) as exc:
        with failing_notify(db):
            svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert x not in db
    # Then 3
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert counts(db) == before
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_eos_c_20__failing_commit_saves_nothing(db, s):
    """EOS-C-20 — a failing commit saves neither the confirm nor the completion.
    Rules: complete_expense_order C10; TC4."""
    E, V = _met_with_draft(db, s)
    before = commit_point(db)
    eid, vid = E.id, V.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 4
    assert reread(db, ExpenseOrder, eid).completed_at is None
    # Then 5
    assert counts(db) == before


@xfail(3062)
def test_eos_c_21__order_read_with_row_lock(db, s):
    """EOS-C-21 — the order is read with a row lock before any check.
    Rules: complete_expense_order C1, C1a [BUG-3062]; HR-10."""
    E, _ = _met_with_draft(db, s)
    eid = E.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.complete_expense_order(db, eo_id=eid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.id == eid
    # Then 2
    assert rec.first_read_lock("expense_orders")
    # Then 3
    assert rec.lock_clause("expense_orders")
    # Then 4
    assert rec.locks_before("expense_orders", "account_invoices")
    # Then 5
    assert rec.locks_before("expense_orders", "expense_order_approvers")


@xfail(3065)
def test_eos_c_22__voided_and_completed_gets_voided_400(db, s):
    """EOS-C-22 — an order both voided and completed gets the "voided" 400, not the unchanged 200.
    Rules: complete_expense_order C3, C2 (check order C1, C3, C2) [BUG-3065]."""
    E = eo(db, s, "1", voided=True, completed=True)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, confirmed=True, linked=True)
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_expense_order(db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Expense order is voided"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, V) == sV
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_c_23__voided_and_completed_never_changed(db, s):
    """EOS-C-23 — an order both voided and completed is never changed (today and after the fix).
    Rules: complete_expense_order C2, C3."""
    E = eo(db, s, "1", voided=True, completed=True)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, confirmed=True, linked=True)
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    eid = E.id

    err = None
    try:
        svc.complete_expense_order(db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id)
    except HTTPException as e:
        err = e

    # Then 1
    assert err is None or err.status_code == 400
    # Then 2
    assert snap(db, E) == sE
    # Then 3
    assert snap(db, V) == sV
    # Then 4
    assert types(db, eid) == []
    # Then 5
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# void_expense_order
# --------------------------------------------------------------------------- #


def test_eos_v_01__voided_committed_updated_by_untouched(db, s):
    """EOS-V-01 — an order with a draft is voided and committed; `updated_by` untouched; nobody told.
    Rules: void_expense_order V9, V11, V12; TC1, TC2."""
    E = eo(db, s, "1", updated_by=s.U1.id)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid = E.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate order"
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == eid
    db.rollback()
    # Then 3
    e = reread(db, ExpenseOrder, eid)
    assert e.voided is True
    assert e.void_note == "Duplicate order"
    assert e.voided_at == NOW
    assert e.voided_by == s.U2.id
    # Then 4
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is None
    assert e.completed_at is None
    # Then 5
    assert reread(db, ExpenseOrder, eid).updated_by == s.U1.id
    # Then 6
    assert notes(db) == []


def test_eos_v_02__draft_deleted_with_lines_and_events(db, s):
    """EOS-V-02 — the draft is deleted with its lines and events.
    Rules: void_expense_order V4, V5."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    VL = invl(db, s, V, 1, "100.00")
    vid = V.id
    commit_point(db)
    eid, vl_id = E.id, VL.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate order"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert gone(db, AccountInvoice, vid)
    # Then 3
    assert gone(db, InvoiceItem, vl_id)
    # Then 4
    assert count_where(db, InvoiceEvent, InvoiceEvent.invoice_id == vid) == 0


@xfail(3070)
def test_eos_v_03__void_events_in_order(db, s):
    """EOS-V-03 — the void's events: approvals cleared, invoice unlinked, then voided.
    Rules: void_expense_order V7 [BUG-3070], V9."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    vid = V.id
    commit_point(db)
    eid, num = E.id, E.expense_number

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate order"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert types(db, eid) == ["approvals_reset", "invoice_voided", "eo_voided"]
    evs = EV(db, eid)
    # Then 3
    assert evs[0].description == RESETVOID
    # Then 4
    assert evs[1].description == f"Invoice unlinked — expense order {num} voided"
    assert evs[1].metadata_json == {"invoice_id": vid}
    # Then 5
    assert evs[2].description == f"Expense order {num} voided. Reason: Duplicate order"
    assert evs[2].metadata_json == {"void_note": "Duplicate order"}
    # Then 6
    assert [e.performed_by for e in EV(db, eid)] == [s.U2.id, s.U2.id, s.U2.id]


def test_eos_v_04__approvals_cleared_with_invoice(db, s):
    """EOS-V-04 — with a linked invoice the approvals are cleared.
    Rules: void_expense_order V7."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    P4 = appr(db, s, E, s.U4)
    inv(db, s, E, linked=True)
    commit_point(db)
    sP4 = snap(db, P4)
    eid, p3_id = E.id, P3.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate order"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    p3 = reread(db, ExpenseOrderApprover, p3_id)
    assert p3.approved is False
    assert p3.approved_at is None
    # Then 3
    assert snap(db, P4) == sP4


def test_eos_v_05__no_recorded_approval_no_reset_event(db, s):
    """EOS-V-05 — no recorded approval: no `approvals_reset` event.
    Rules: void_expense_order V7."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    inv(db, s, E, linked=True)
    commit_point(db)
    eid = E.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate order"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert types(db, eid) == ["invoice_voided", "eo_voided"]


def test_eos_v_06__already_voided_400(db, s):
    """EOS-V-06 — already voided: 400, the extra row is gone.
    Rules: void_expense_order V2, Errors row 2; TC3."""
    E = eo(db, s, "1", voided=True)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.void_expense_order(
                db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Again"
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Expense order is already voided"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, E) == sE
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_v_07__completed_order_400(db, s):
    """EOS-V-07 — a completed order with its confirmed invoice: the "completed" 400, nothing written.
    Rules: void_expense_order V3, V6a (V3 first), Errors row 3."""
    E = eo(db, s, "1", completed=True)
    line(db, E, 1, "100.00")
    V = inv(db, s, E, confirmed=True, linked=True)
    before = commit_point(db)
    sE, sV = snap(db, E), snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_expense_order(
            db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a completed expense order"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, V) == sV
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


@xfail(639)
def test_eos_v_08__draft_with_payment_history_400(db, s):
    """EOS-V-08 — a draft with payment history: the invoice manager's 400, the whole void undone.
    Rules: void_expense_order V5, Errors row 4 [BUG-639] (invoice manager pass-through)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    pay(db, s, V, "100.00", voided=True)
    commit_point(db)
    sE, sV = snap(db, E), snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_expense_order(
            db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == PAYHIST
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert snap(db, V) == sV


def test_eos_v_09__draft_with_payment_history_never_deleted(db, s):
    """EOS-V-09 — a draft with payment history is never deleted and the order not voided (today and after the fix).
    Rules: void_expense_order V5; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    P = pay(db, s, V, "100.00", voided=True)
    commit_point(db)
    sE = snap(db, E)
    eid, vid, pid = E.id, V.id, P.id
    x, x_id = mk_x(db)

    with pytest.raises(Exception):
        svc.void_expense_order(
            db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )

    # Then 1
    assert x not in db
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v is not None
    assert v.invoice_status == "draft"
    # Then 3
    p = reread(db, InvoicePayment, pid)
    assert p is not None
    assert p.is_voided is True
    # Then 4
    assert snap(db, E) == sE
    # Then 5
    assert types(db, eid) == []
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_eos_v_10__voided_invoice_untouched_order_unlinked(db, s):
    """EOS-V-10 — a linked invoice already voided is not touched; the order is voided and unlinked, with the intended event texts.
    Rules: void_expense_order V6, V7, V9."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, voided_inv=True, linked=True)
    vid = V.id
    commit_point(db)
    sV = snap(db, V)
    eid, p3_id, num = E.id, P3.id, E.expense_number

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert snap(db, V) == sV
    # Then 3
    e = reread(db, ExpenseOrder, eid)
    assert e.voided is True
    assert e.invoice_id is None
    # Then 4
    assert reread(db, ExpenseOrderApprover, p3_id).approved is False
    # Then 5
    assert types(db, eid) == ["approvals_reset", "invoice_voided", "eo_voided"]
    assert EV(db, eid)[1].metadata_json == {"invoice_id": vid}
    # Then 6
    assert EV(db, eid)[0].description == RESETVOID
    # Then 7
    assert EV(db, eid)[1].description == f"Invoice unlinked — expense order {num} voided"
    # Then 8
    assert EV(db, eid)[2].description == f"Expense order {num} voided. Reason: Cancelled"
    # Then 9
    assert EV(db, eid)[2].metadata_json == {"void_note": "Cancelled"}
    # Then 10
    assert [e.performed_by for e in EV(db, eid)] == [s.U2.id, s.U2.id, s.U2.id]


def test_eos_v_11__w2_invoice_untouched_order_unlinked(db, s):
    """EOS-V-11 — a linked W2 invoice is not touched; the order is voided and unlinked.
    Rules: void_expense_order V4, V6, V7; HR-16."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    Z = inv(db, s, E, ws="2", linked=True)
    ZL = invl(db, s, Z, 1, "100.00")
    commit_point(db)
    sZ, sZL = snap(db, Z), snap(db, ZL)
    eid = E.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert snap(db, Z) == sZ
    # Then 3
    assert snap(db, ZL) == sZL
    # Then 4
    e = reread(db, ExpenseOrder, eid)
    assert e.voided is True
    assert e.invoice_id is None
    # Then 5
    assert types(db, eid) == ["invoice_voided", "eo_voided"]


def test_eos_v_12__w0_invoice_untouched_order_unlinked(db, s):
    """EOS-V-12 — a linked W0 invoice is not touched; the order is voided and unlinked.
    Rules: void_expense_order V4, V6; HR-16."""
    Z = inv(db, s, None, ws="0")
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    link(db, E, Z)
    commit_point(db)
    sZ = snap(db, Z)
    eid = E.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert snap(db, Z) == sZ
    # Then 3
    e = reread(db, ExpenseOrder, eid)
    assert e.voided is True
    assert e.invoice_id is None


@xfail(3069)
def test_eos_v_13__confirmed_invoice_refuses_void(db, s):
    """EOS-V-13 — a confirmed invoice refuses the void; order, approvals, invoice and payments kept.
    Rules: void_expense_order V6a, Errors row 5 [BUG-3069]."""
    E = eo(db, s, "1")
    line(db, E, 1, "20.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    V = inv(
        db, s, E, confirmed=True, invoice_amount=Decimal("20.00"),
        paid_amount=Decimal("10.00"), payment_status="partial", linked=True,
    )
    P = pay(db, s, V, "10.00")
    before = commit_point(db)
    sE, sP3, sV, sP = snap(db, E), snap(db, P3), snap(db, V), snap(db, P)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_expense_order(
            db, eo_id=E.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == FINAL
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert snap(db, P3) == sP3
    # Then 8
    assert snap(db, V) == sV
    # Then 9
    assert snap(db, P) == sP
    # Then 10
    assert counts(db) == before
    db.rollback()
    # Then 11
    assert x_gone(db, x_id)


def test_eos_v_14__confirmed_invoice_never_changed(db, s):
    """EOS-V-14 — a confirmed invoice is never deleted or changed by the void (today and after the fix).
    Rules: void_expense_order V5, V6a."""
    E = eo(db, s, "1")
    line(db, E, 1, "20.00")
    V = inv(db, s, E, confirmed=True, invoice_amount=Decimal("20.00"), linked=True)
    P = pay(db, s, V, "10.00")
    commit_point(db)
    sP = snap(db, P)
    eid, vid = E.id, V.id

    try:
        svc.void_expense_order(
            db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    except HTTPException:
        pass

    # Then 1
    v = reread(db, AccountInvoice, vid)
    assert v is not None
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("20.00")
    # Then 2
    assert snap(db, P) == sP
    # Then 3
    assert count_where(db, InvoicePayment, InvoicePayment.invoice_id == vid) == 1


@xfail(3067)
def test_eos_v_15__no_invoice_approvals_cleared(db, s):
    """EOS-V-15 — without an invoice, the approvals are cleared the same way.
    Rules: void_expense_order V8 [BUG-3067]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid, p3_id = E.id, P3.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).voided is True
    # Then 3
    p3 = reread(db, ExpenseOrderApprover, p3_id)
    assert p3.approved is False
    assert p3.approved_at is None
    # Then 4
    assert types(db, eid) == ["approvals_reset", "eo_voided"]
    # Then 5
    assert EV(db, eid)[0].description == RESETVOID


def test_eos_v_16__no_invoice_voided_no_unlink_event(db, s):
    """EOS-V-16 — without an invoice: voided, no `invoice_voided` event (today and after the fix).
    Rules: void_expense_order V8, V9."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid = E.id

    result = svc.void_expense_order(
        db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
    )

    # Then 1
    assert result.id == eid
    db.rollback()
    # Then 2
    e = reread(db, ExpenseOrder, eid)
    assert e.voided is True
    assert e.void_note == "Cancelled"
    assert e.voided_by == s.U2.id
    assert e.voided_at == NOW
    assert e.invoice_id is None
    # Then 3
    assert "invoice_voided" not in types(db, eid)
    # Then 4
    assert types(db, eid)[-1] == "eo_voided"


@xfail(3064)
@pytest.mark.parametrize(
    "note",
    [
        pytest.param("   ", id="EOS-V-17"),
        pytest.param("", id="EOS-V-18"),
    ],
)
def test_eos_v_17_18__schema_rejects_blank_note(note):
    """EOS-V-17 / EOS-V-18 — the schema rejects a spaces-only / empty void note.
    Rules: void_expense_order V10, Errors row 6 [BUG-3064]."""
    # Then 1
    with pytest.raises(ValidationError):
        ExpenseOrderVoidRequest(void_note=note)


@xfail(3064)
def test_eos_v_19__schema_trims_padded_note():
    """EOS-V-19 — the schema trims a padded void note.
    Rules: void_expense_order V10 [BUG-3064]."""
    result = ExpenseOrderVoidRequest(void_note="  Duplicate  ")

    # Then 1
    assert result.void_note == "Duplicate"


def test_eos_v_20__schema_keeps_plain_note():
    """EOS-V-20 — the schema keeps a plain void note as typed.
    Rules: void_expense_order V10."""
    result = ExpenseOrderVoidRequest(void_note="Duplicate order")

    # Then 1
    assert result.void_note == "Duplicate order"


def test_eos_v_21__missing_order_404(db, s):
    """EOS-V-21 — a missing order: 404, the extra row is gone.
    Rules: void_expense_order V1, Errors row 1; TC3."""
    E = eo(db, s, "1")
    commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_expense_order(
            db, eo_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_v_22__w2_order_404(db, s):
    """EOS-V-22 — another workspace's order (W2): 404, not voided.
    Rules: void_expense_order V1; HR-16."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2")
    commit_point(db)
    sZ = snap(db, Z)
    zid = Z.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_expense_order(
            db, eo_id=zid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 4
    assert snap(db, Z) == sZ


def test_eos_v_23__failing_commit_keeps_everything(db, s):
    """EOS-V-23 — a failing commit keeps the order, its draft and its approvals.
    Rules: void_expense_order V9; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    VL = invl(db, s, V, 1, "100.00")
    before = commit_point(db)
    sE, sV, sVL, sP3 = snap(db, E), snap(db, V), snap(db, VL), snap(db, P3)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.void_expense_order(
                db, eo_id=eid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled"
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert snap(db, V) == sV
    # Then 5
    assert snap(db, VL) == sVL
    # Then 6
    assert snap(db, P3) == sP3
    # Then 7
    assert counts(db) == before


@xfail(3062)
def test_eos_v_24__order_read_with_row_lock(db, s):
    """EOS-V-24 — the order is read with a row lock before the checks.
    Rules: void_expense_order V1, V1a [BUG-3062]; HR-10."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    inv(db, s, E, linked=True)
    eid = E.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.void_expense_order(
            db, eo_id=eid, workspace_id=w1_id, user_id=u2_id, void_note="Cancelled"
        )

    # Then 1
    assert result.id == eid
    # Then 2
    assert rec.first_read_lock("expense_orders")
    # Then 3
    assert rec.lock_clause("expense_orders")
    # Then 4
    assert rec.locks_before("expense_orders", "account_invoices")


# --------------------------------------------------------------------------- #
# add_item
# --------------------------------------------------------------------------- #


def _fee():
    return ExpenseOrderItemCreate(
        description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")
    )


def test_eos_ai_01__line_added_stamped_committed(db, s):
    """EOS-AI-01 — a line is added, stamped and committed; no invoice while approvals are not met.
    Rules: add_item L1, L2; TC1, TC2."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3)
    commit_point(db)
    eid = E.id

    result = svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, ExpenseOrderItem)
    assert result.expense_order_id == eid
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, ExpenseOrderItem, rid)
    assert row.description == "Fee"
    assert row.line_subtotal == Decimal("50.00")
    # Then 4
    e = reread(db, ExpenseOrder, eid)
    assert e.items_updated_at == NOW
    assert e.invoice_id is None
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == eid) == 0
    # Then 6
    assert notes(db) == []


def test_eos_ai_02__linked_draft_gets_new_line(db, s):
    """EOS-AI-02 — a linked draft gets the new line set.
    Rules: add_item L2; _sync_or_create_invoice Y2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid, vid = E.id, V.id

    result = svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.expense_order_id == eid
    db.rollback()
    # Then 2
    assert [l.line_subtotal for l in LINES(db, vid)] == [Decimal("100.00"), Decimal("50.00")]
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_amount == Decimal("150.00")
    assert v.invoice_status == "draft"
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == eid) == 1


def test_eos_ai_03__waived_first_line_drafts_invoice(db, s):
    """EOS-AI-03 — a waived order with an account gets its draft on the first line, and the draft notice.
    Rules: add_item L2; _sync_or_create_invoice Y7."""
    E = eo(db, s, "1", waived=True)
    commit_point(db)
    eid = E.id

    result = svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.expense_order_id == eid
    db.rollback()
    # Then 2
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is not None
    inv_id = e.invoice_id
    # Then 3
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("50.00")
    # Then 4
    assert recips(db) == [s.U1.id]
    # Then 5
    assert notes(db)[0].preview == DRAFTP
    assert notes(db)[0].notification_type == "invoice_action"


def test_eos_ai_04__wiping_line_no_notice(db, s):
    """EOS-AI-04 — a line that wipes approvals writes no notification.
    Rules: add_item L3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid, p3_id = E.id, P3.id

    result = svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.expense_order_id == eid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrderApprover, p3_id).approved is False
    # Then 3
    assert notes(db) == []


def test_eos_ai_05__missing_order_404(db, s):
    """EOS-AI-05 — a missing order: 404 passes unchanged, the extra row is gone.
    Rules: add_item L1; TC3."""
    eo(db, s, "1")
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.add_item(
                db, eo_id=MISSING, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_ai_06__draft_refused_undoes_line(db, s):
    """EOS-AI-06 — the draft step refusing the account undoes the new line.
    Rules: add_item L2; _create_draft_invoice D4; TC3."""
    A3 = acct(db, s, "No Bills", allow_invoices=False)
    E = eo(db, s, "1", waived=True, account_id=A3.id)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)
    eid = E.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert count_where(db, ExpenseOrderItem, ExpenseOrderItem.expense_order_id == eid) == 0
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_ai_07__failing_commit_no_line(db, s):
    """EOS-AI-07 — a failing commit keeps the order without the line.
    Rules: add_item L1; TC4."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3)
    before = commit_point(db)
    sE = snap(db, E)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_item(db, eo_id=eid, item_in=_fee(), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# update_item
# --------------------------------------------------------------------------- #


def _price(p):
    return ExpenseOrderItemUpdate(unit_price=Decimal(p))


def test_eos_ui_01__price_change_committed_draft_follows(db, s):
    """EOS-UI-01 — a price change is committed; the order is stamped and its draft follows.
    Rules: update_item L4, L5; TC1, TC2."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid, vid, l1_id = E.id, V.id, L1.id

    result = svc.update_item(
        db, item_id=l1_id, item_in=_price("80.00"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == l1_id
    db.rollback()
    # Then 3
    row = reread(db, ExpenseOrderItem, l1_id)
    assert row.unit_price == Decimal("80.00")
    assert row.line_subtotal == Decimal("80.00")
    # Then 4
    assert reread(db, ExpenseOrder, eid).items_updated_at == NOW
    # Then 5
    assert [l.line_subtotal for l in LINES(db, vid)] == [Decimal("80.00")]
    # Then 6
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("80.00")
    # Then 7
    assert notes(db) == []


def test_eos_ui_02__noop_still_stamps_and_resyncs(db, s):
    """EOS-UI-02 — a call that changes nothing still stamps the order and resyncs the draft.
    Rules: update_item L5."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid, vid, l1_id = E.id, V.id, L1.id

    result = svc.update_item(
        db, item_id=l1_id, item_in=_price("100.00"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == l1_id
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).items_updated_at == NOW
    # Then 3
    assert itypes(db, vid).count("items_synced") == 1


def test_eos_ui_03__only_own_order_stamped(db, s):
    """EOS-UI-03 — only the line's own order is stamped and resynced.
    Rules: update_item L5."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    VE = inv(db, s, E, linked=True)
    invl(db, s, VE, 1, "100.00")
    F = eo(db, s, "2")
    LF = line(db, F, 1, "30.00")
    commit_point(db)
    eid, fid, ve_id, lf_id = E.id, F.id, VE.id, LF.id

    result = svc.update_item(
        db, item_id=lf_id, item_in=_price("35.00"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == lf_id
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, fid).items_updated_at == NOW
    # Then 3
    assert reread(db, ExpenseOrder, eid).items_updated_at is None
    # Then 4
    assert itypes(db, ve_id) == []


def test_eos_ui_04__wiping_edit_no_notice(db, s):
    """EOS-UI-04 — a line edit that wipes approvals writes no notification.
    Rules: update_item L5 (no notification, as L3)."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    l1_id, p3_id = L1.id, P3.id

    result = svc.update_item(
        db, item_id=l1_id, item_in=_price("80.00"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == l1_id
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrderApprover, p3_id).approved is False
    # Then 3
    assert notes(db) == []


def test_eos_ui_05__missing_line_404(db, s):
    """EOS-UI-05 — a missing line: 404 passes unchanged, the extra row is gone.
    Rules: update_item L4; TC3."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    commit_point(db)
    sL1 = snap(db, L1)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_item(
                db, item_id=MISSING, item_in=_price("80.00"), workspace_id=s.W1.id, user_id=s.U2.id
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order item not found"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, L1) == sL1
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_ui_06__failing_commit_keeps_old_price(db, s):
    """EOS-UI-06 — a failing commit keeps the old price and the old draft.
    Rules: update_item L4; TC4."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    VL = invl(db, s, V, 1, "100.00")
    commit_point(db)
    sL1, sVL = snap(db, L1), snap(db, VL)
    eid, l1_id = E.id, L1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_item(
                db, item_id=l1_id, item_in=_price("80.00"), workspace_id=s.W1.id, user_id=s.U2.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, L1) == sL1
    # Then 4
    assert snap(db, VL) == sVL
    # Then 5
    assert reread(db, ExpenseOrder, eid).items_updated_at is None


# --------------------------------------------------------------------------- #
# remove_item
# --------------------------------------------------------------------------- #


def test_eos_ri_01__line_removed_returned_readable(db, s):
    """EOS-RI-01 — the line is removed and committed; the deleted line is returned, its fields readable.
    Rules: remove_item L6, L7; TC1."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    L2 = line(db, E, 2, "50.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    invl(db, s, V, 2, "50.00")
    commit_point(db)
    eid, vid, l2_id = E.id, V.id, L2.id

    result = svc.remove_item(db, item_id=l2_id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.expense_order_id == eid
    assert result.line_number == 2
    db.rollback()
    # Then 2
    assert gone(db, ExpenseOrderItem, l2_id)
    # Then 3
    assert reread(db, ExpenseOrder, eid).items_updated_at == NOW
    # Then 4
    assert [l.line_subtotal for l in LINES(db, vid)] == [Decimal("100.00")]
    # Then 5
    assert notes(db) == []


def test_eos_ri_02__last_line_leaves_zero_draft(db, s):
    """EOS-RI-02 — removing the last line leaves a 0.00 draft with no lines.
    Rules: remove_item L6."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    eid, vid, l1_id = E.id, V.id, L1.id

    result = svc.remove_item(db, item_id=l1_id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.line_number == 1
    db.rollback()
    # Then 2
    assert LINES(db, vid) == []
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("0.00")
    # Then 4
    assert reread(db, ExpenseOrder, eid).invoice_id == vid


def test_eos_ri_03__missing_line_404(db, s):
    """EOS-RI-03 — a missing line: 404, the extra row is gone.
    Rules: remove_item L6, L6a; TC3."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    commit_point(db)
    sL1 = snap(db, L1)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.remove_item(db, item_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    # Then 3
    assert x not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, L1) == sL1
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_ri_04__failing_commit_keeps_line(db, s):
    """EOS-RI-04 — a failing commit keeps the line and the draft's lines.
    Rules: remove_item L7; TC4."""
    E = eo(db, s, "1")
    L1 = line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    VL = invl(db, s, V, 1, "100.00")
    commit_point(db)
    sL1, sVL = snap(db, L1), snap(db, VL)
    l1_id = L1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_item(db, item_id=l1_id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, L1) == sL1
    # Then 4
    assert snap(db, VL) == sVL


def test_eos_ri_05__w2_line_404(db, s):
    """EOS-RI-05 — another workspace's line (W2): the same 404, the line kept.
    Rules: remove_item L6a; TC3."""
    Z2 = eo(db, s, "9", ws="2")
    L9 = line(db, Z2, 1, "100.00")
    before = commit_point(db)
    sL9, sZ2 = snap(db, L9), snap(db, Z2)
    x, x_id = mk_x(db)
    l9_id = L9.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=l9_id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Expense order item not found"
    # Then 3
    assert x not in db
    # Then 4
    assert snap(db, L9) == sL9
    # Then 5
    assert snap(db, Z2) == sZ2
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# --------------------------------------------------------------------------- #
# get_items
# --------------------------------------------------------------------------- #


def test_eos_gi_01__lines_by_number_no_commit(db, s):
    """EOS-GI-01 — returns the order's lines by line number; neither commits nor rolls back.
    Rules: get_items L8; TC6."""
    E = eo(db, s, "1")
    L3 = line(db, E, 3, "30.00")
    L1 = line(db, E, 1, "10.00")
    F = eo(db, s, "2")
    line(db, F, 1, "99.00")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_items(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert [x.id for x in result] == [L1.id, L3.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_eos_gi_02__w2_order_404_no_rollback(db, s):
    """EOS-GI-02 — another workspace's order: 404, no rollback.
    Rules: get_items L8; TC6."""
    Z = eo(db, s, "9", ws="2")
    line(db, Z, 1, "10.00")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)

    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_items(db, eo_id=zid, workspace_id=s.W1.id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# _invoice_item_dicts (transient lines only)
# --------------------------------------------------------------------------- #


def _tl(id_, k, desc, qty, unit, price, sub):
    return ExpenseOrderItem(
        id=id_,
        line_number=k,
        description=desc,
        quantity=qty,
        unit=unit,
        unit_price=price,
        line_subtotal=sub,
    )


def test_eos_s_01__one_dict_per_line_all_fields(db, s):
    """EOS-S-01 — one dict per line, renumbered 1…N, every field mapped.
    Rules: _invoice_item_dicts Returns, S1, S3, S4, S5."""
    a = _tl(501, 1, "Rent", Decimal("1"), None, Decimal("100.00"), Decimal("100.00"))
    b = _tl(502, 3, "Water", Decimal("2"), "month", Decimal("12.50"), Decimal("25.00"))
    c = _tl(503, 4, "Gas", Decimal("0.5"), "kg", Decimal("8.00"), Decimal("4.00"))

    result = svc._invoice_item_dicts([a, b, c])

    # Then 1
    assert [d["line_number"] for d in result] == [1, 2, 3]
    # Then 2
    assert [d["description"] for d in result] == ["Rent", "Water", "Gas"]
    # Then 3
    assert [d["source_order_item_id"] for d in result] == [501, 502, 503]
    # Then 4
    assert [d["item_id"] for d in result] == [None, None, None]
    assert [d["source_order_item_type"] for d in result] == ["eo_item", "eo_item", "eo_item"]
    # Then 5
    assert [d["unit"] for d in result] == [None, "month", "kg"]
    # Then 6
    assert [d["quantity"] for d in result] == [Decimal("1"), Decimal("2"), Decimal("0.5")]
    # Then 7
    assert [d["unit_price"] for d in result] == [
        Decimal("100.00"),
        Decimal("12.50"),
        Decimal("8.00"),
    ]
    # Then 8
    assert [d["line_subtotal"] for d in result] == [
        Decimal("100.00"),
        Decimal("25.00"),
        Decimal("4.00"),
    ]


def test_eos_s_02__given_order_kept(db, s):
    """EOS-S-02 — the given order is kept, not the stored line numbers.
    Rules: _invoice_item_dicts S1."""
    a = _tl(601, 7, "Late", Decimal("1"), None, Decimal("1.00"), Decimal("1.00"))
    b = _tl(602, 2, "Early", Decimal("1"), None, Decimal("2.00"), Decimal("2.00"))

    result = svc._invoice_item_dicts([a, b])

    # Then 1
    assert [(d["line_number"], d["source_order_item_id"]) for d in result] == [
        (1, 601),
        (2, 602),
    ]


@pytest.mark.parametrize(
    ("id_", "desc", "expected"),
    [
        pytest.param(502, "", "Expense item 502", id="EOS-S-03"),
        pytest.param(503, None, "Expense item 503", id="EOS-S-04"),
        pytest.param(504, " ", " ", id="EOS-S-05"),
    ],
)
def test_eos_s_03_05__description_fallback(db, s, id_, desc, expected):
    """EOS-S-03 / S-04 / S-05 — an empty / None description becomes "Expense item <line id>"; one space is kept.
    Rules: _invoice_item_dicts S2."""
    a = _tl(id_, 1, desc, Decimal("1"), None, Decimal("1.00"), Decimal("1.00"))

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["description"] == expected


def test_eos_s_06__quantity_zero_becomes_one(db, s):
    """EOS-S-06 — quantity 0 becomes 1; the subtotal stays as stored.
    Rules: _invoice_item_dicts S4, S5."""
    a = _tl(505, 1, "Old", Decimal("0"), None, Decimal("7.00"), Decimal("0.00"))

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["quantity"] == Decimal(1)
    # Then 2
    assert result[0]["line_subtotal"] == Decimal("0.00")
    assert result[0]["unit_price"] == Decimal("7.00")


def test_eos_s_07__quantity_none_becomes_one(db, s):
    """EOS-S-07 — quantity None becomes 1.
    Rules: _invoice_item_dicts S4."""
    a = _tl(506, 1, "Old", None, None, Decimal("7.00"), Decimal("7.00"))

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["quantity"] == Decimal(1)


def test_eos_s_08__quantity_small_kept(db, s):
    """EOS-S-08 — quantity 0.01 is kept.
    Rules: _invoice_item_dicts S4."""
    a = _tl(507, 1, "Tiny", Decimal("0.01"), None, Decimal("7.00"), Decimal("0.07"))

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["quantity"] == Decimal("0.01")


def test_eos_s_09__price_and_subtotal_none_become_zero(db, s):
    """EOS-S-09 — price and subtotal None become 0.
    Rules: _invoice_item_dicts S5."""
    a = _tl(508, 1, "Free", Decimal("2"), None, None, None)

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["unit_price"] == Decimal(0)
    # Then 2
    assert result[0]["line_subtotal"] == Decimal(0)
    # Then 3
    assert result[0]["quantity"] == Decimal("2")


def test_eos_s_10__no_rounding_no_recompute(db, s):
    """EOS-S-10 — no rounding and no recomputation of the subtotal.
    Rules: _invoice_item_dicts S5."""
    a = _tl(509, 1, "Odd", Decimal("2"), None, Decimal("3.333"), Decimal("5.00"))

    result = svc._invoice_item_dicts([a])

    # Then 1
    assert result[0]["unit_price"] == Decimal("3.333")
    # Then 2
    assert result[0]["line_subtotal"] == Decimal("5.00")


def test_eos_s_11__empty_list(db, s):
    """EOS-S-11 — an empty list gives an empty list.
    Rules: _invoice_item_dicts S6."""
    result = svc._invoice_item_dicts([])

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# _create_draft_invoice
# --------------------------------------------------------------------------- #


def test_eos_d_01__draft_carries_order_fields(db, s):
    """EOS-D-01 — the draft carries the order's account, due date, notes and link fields.
    Rules: _create_draft_invoice D2, D2a, D6."""
    E = eo(db, s, "1", due_date=date(2026, 10, 15))
    line(db, E, 1, "100.00")
    commit_point(db)
    eid, num = E.id, E.expense_number

    result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == eid
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    # Then 2
    v = reread(db, AccountInvoice, inv_id)
    assert v.workspace_id == s.W1.id
    assert v.account_id == s.A1.id
    assert v.invoice_type == "payable"
    assert v.invoice_status == "draft"
    # Then 3
    v = reread(db, AccountInvoice, inv_id)
    assert v.order_type == "expense_order"
    assert v.order_id == eid
    assert v.due_date == date(2026, 10, 15)
    # Then 4
    v = reread(db, AccountInvoice, inv_id)
    assert v.description == f"Auto-created from expense order {num}"
    assert v.notes == "Office rent"
    assert v.allow_payments is True
    # Then 5
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_number is None
    assert v.vendor_invoice_number is None
    assert v.payment_locked_reason is None
    # Then 6
    assert reread(db, ExpenseOrder, eid).invoice_id == inv_id
    # Then 7
    assert reread(db, AccountInvoice, inv_id).created_by == s.U2.id


def test_eos_d_02__lines_mirror_order_amount_is_sum(db, s):
    """EOS-D-02 — the draft's lines mirror the order's lines; amount is their sum.
    Rules: _create_draft_invoice D2 (amount follows the lines), D6."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    line(db, E, 3, "25.50")
    commit_point(db)

    result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    # Then 2
    assert [l.line_number for l in LINES(db, inv_id)] == [1, 2]
    # Then 3
    assert [l.line_subtotal for l in LINES(db, inv_id)] == [Decimal("100.00"), Decimal("25.50")]
    # Then 4
    assert reread(db, AccountInvoice, inv_id).invoice_amount == Decimal("125.50")
    # Then 5
    assert itypes(db, inv_id) == ["created", "items_synced"]


def test_eos_d_03__one_invoice_created_event_no_notice(db, s):
    """EOS-D-03 — one `invoice_created` order event; no notification.
    Rules: _create_draft_invoice D7, D8."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)
    eid = E.id

    result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    # Then 2
    assert types(db, eid) == ["invoice_created"]
    # Then 3
    evs = EV(db, eid)
    assert evs[0].description == f"Invoice #{inv_id} created from expense order"
    assert evs[0].metadata_json == {"invoice_id": inv_id}
    assert evs[0].performed_by == s.U2.id
    # Then 4
    assert notes(db) == []


def test_eos_d_04__no_lines_zero_draft(db, s):
    """EOS-D-04 — an order with no lines gives a 0.00 draft with no lines.
    Rules: _create_draft_invoice D6."""
    E = eo(db, s, "1")
    commit_point(db)

    result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    # Then 2
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_amount == Decimal("0.00")
    assert v.invoice_status == "draft"
    # Then 3
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == inv_id) == 0


def test_eos_d_05__no_account_422(db, s):
    """EOS-D-05 — no account: 422, nothing written.
    Rules: _create_draft_invoice D1."""
    E = eo(db, s, "1", account_id=None)
    line(db, E, 1, "100.00")
    before = commit_point(db)
    sE = snap(db, E)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Set an account on the expense order before creating an invoice"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap(db, E) == sE


@pytest.mark.parametrize(
    ("acct_but", "status", "detail"),
    [
        pytest.param(
            {"is_deleted": True}, 400, "Cannot create invoice for deleted account", id="EOS-D-06"
        ),
        pytest.param(
            {"is_active": False}, 400, "Cannot create invoice for inactive account", id="EOS-D-07"
        ),
        pytest.param(
            {"allow_invoices": False}, 403, "Invoices are not allowed for this account", id="EOS-D-08"
        ),
    ],
)
def test_eos_d_06_08__account_refusal_passes(db, s, acct_but, status, detail):
    """EOS-D-06 / D-07 / D-08 — a deleted / inactive / no-invoices account: the invoice manager's refusal passes unchanged.
    Rules: _create_draft_invoice D4, R4a (deleted = `is_deleted True`)."""
    names = {"is_deleted": "Old Vendor", "is_active": "Sleepy", "allow_invoices": "No Bills"}
    AX = acct(db, s, names[next(iter(acct_but))], **acct_but)
    E = eo(db, s, "1", account_id=AX.id)
    commit_point(db)
    w1_id = s.W1.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            svc._create_draft_invoice(db, eo=E, workspace_id=w1_id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == status
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == w1_id) == 0


def test_eos_d_09__w2_account_becomes_422(db, s):
    """EOS-D-09 — a W2 account becomes the 422 "not found in this workspace", the 404 as its cause.
    Rules: _create_draft_invoice D5; HR-16."""
    E = eo(db, s, "1", account_id=s.A9.id)
    commit_point(db)
    w1_id, w2_id = s.W1.id, s.W2.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            svc._create_draft_invoice(db, eo=E, workspace_id=w1_id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert (
        exc.value.detail
        == "Cannot create invoice: selected account was not found in this workspace"
    )
    # Then 4
    assert isinstance(exc.value.__cause__, HTTPException)
    assert exc.value.__cause__.status_code == 404
    # Then 5
    assert (
        count_where(db, AccountInvoice, AccountInvoice.workspace_id.in_([w1_id, w2_id])) == 0
    )


def test_eos_d_10__w0_account_becomes_422(db, s):
    """EOS-D-10 — a W0 account becomes the same 422.
    Rules: _create_draft_invoice D5; HR-16."""
    E = eo(db, s, "1", account_id=s.A0.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert (
        exc.value.detail
        == "Cannot create invoice: selected account was not found in this workspace"
    )


@xfail(3063)
def test_eos_d_11__invoice_date_is_utc_date(db, s):
    """EOS-D-11 — the order's invoice date is the UTC date.
    Rules: _create_draft_invoice D3 [BUG-3063]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)

    result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert reread(db, AccountInvoice, result.invoice_id).invoice_date == date(2026, 9, 27)


# [claude] EOS-D-12
@xfail(627)
def test_eos_d_12__no_invoice_amount_sent(db, s):
    """EOS-D-12 — no invoice amount is sent to the invoice manager.
    Rules: _create_draft_invoice D2 [BUG-627]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)
    aim = svc.account_invoice_manager

    with patch.object(aim, "create_invoice", wraps=aim.create_invoice) as ci:
        result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert "invoice_amount" not in ci.call_args.kwargs["invoice_data"].model_fields_set


def test_eos_d_13__flushed_never_committed(db, s):
    """EOS-D-13 — the draft is flushed, never committed.
    Rules: _create_draft_invoice Persistence (flush only)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)
    w1_id = s.W1.id

    with spies(db) as (cm, rb):
        result = svc._create_draft_invoice(db, eo=E, workspace_id=w1_id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    db.rollback()
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == w1_id) == 0


def test_eos_d_14__create_invoice_called_once_by_keyword(db, s):
    """EOS-D-14 — `create_invoice` is called once, by keyword.
    Rules: _create_draft_invoice D2a."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)
    aim = svc.account_invoice_manager

    with patch.object(aim, "create_invoice", wraps=aim.create_invoice) as ci:
        result = svc._create_draft_invoice(db, eo=E, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert ci.call_count == 1
    assert ci.call_args.args == ()
    # Then 3
    assert set(ci.call_args.kwargs) == {"session", "invoice_data", "workspace_id", "user_id"}
    # Then 4
    assert ci.call_args.kwargs["session"] is db
    assert ci.call_args.kwargs["workspace_id"] == s.W1.id
    assert ci.call_args.kwargs["user_id"] == s.U2.id
    # Then 5
    assert type(ci.call_args.kwargs["invoice_data"]).__name__ == "AccountInvoiceCreate"


# --------------------------------------------------------------------------- #
# _resync_draft_invoice
# --------------------------------------------------------------------------- #


def _resync(db, s, E, V):
    svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=s.W1.id, user_id=s.U2.id)


def test_eos_r_01__lines_replaced(db, s):
    """EOS-R-01 — the draft's lines are replaced by the order's current lines.
    Rules: _resync_draft_invoice R1."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    line(db, E, 4, "50.00")
    V = inv(db, s, E, notes="Office rent", linked=True)
    invl(db, s, V, 1, "999.00")
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert [(l.line_number, l.line_subtotal) for l in LINES(db, vid)] == [
        (1, Decimal("100.00")),
        (2, Decimal("50.00")),
    ]
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("150.00")
    # Then 3
    assert itypes(db, vid) == ["items_synced"]


def test_eos_r_02__nothing_differs_no_header_update(db, s):
    """EOS-R-02 — nothing differs: still one `items_synced` event, no header update.
    Rules: _resync_draft_invoice R1, R5."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, notes="Office rent", linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert itypes(db, vid) == ["items_synced"]
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.account_id == s.A1.id
    assert v.due_date is None
    assert v.notes == "Office rent"


def test_eos_r_03__due_date_copied(db, s):
    """EOS-R-03 — a different due date is copied in one header update.
    Rules: _resync_draft_invoice R2, R5."""
    E = eo(db, s, "1", due_date=date(2026, 10, 15))
    V = inv(db, s, E, due_date=date(2026, 10, 1), notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).due_date == date(2026, 10, 15)
    # Then 2
    assert itypes(db, vid).count("item_manually_updated") == 1


def test_eos_r_04__order_due_date_cleared_clears_invoice(db, s):
    """EOS-R-04 — the order's due date cleared: the invoice's due date is cleared too.
    Rules: _resync_draft_invoice R2, R2a (the order's `due_date` is NULL on the row; works today)."""
    E = eo(db, s, "1")
    V = inv(db, s, E, due_date=date(2026, 10, 1), notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).due_date is None


def test_eos_r_05__description_replaces_notes(db, s):
    """EOS-R-05 — a different non-empty description replaces the notes.
    Rules: _resync_draft_invoice R3."""
    E = eo(db, s, "1", description="Water bill")
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).notes == "Water bill"
    # Then 2
    assert itypes(db, vid).count("item_manually_updated") == 1


def test_eos_r_06__empty_description_keeps_notes(db, s):
    """EOS-R-06 — an empty order description never clears the notes.
    Rules: _resync_draft_invoice R3, R5."""
    E = eo(db, s, "1")
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id
    E.description = ""

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).notes == "Office rent"
    # Then 2
    assert "item_manually_updated" not in itypes(db, vid)


def test_eos_r_07__other_account_moves_draft(db, s):
    """EOS-R-07 — another account moves the draft to it.
    Rules: _resync_draft_invoice R4, R5."""
    E = eo(db, s, "1", account_id=s.A2.id)
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).account_id == s.A2.id
    # Then 2
    assert itypes(db, vid).count("item_manually_updated") == 1


@xfail(629)
@pytest.mark.parametrize(
    ("acct_but", "status", "detail"),
    [
        pytest.param(
            {"is_active": False}, 400, "Cannot assign invoice to inactive account", id="EOS-R-08"
        ),
        pytest.param(
            {"allow_invoices": False}, 403, "Invoices are not allowed for this account", id="EOS-R-09"
        ),
    ],
)
def test_eos_r_08_09__account_refused(db, s, acct_but, status, detail):
    """EOS-R-08 / R-09 — an inactive account is refused with the invoice manager's 400 / one that does not allow invoices with 403.
    Rules: _resync_draft_invoice R4b [BUG-629]."""
    names = {"is_active": "Sleepy", "allow_invoices": "No Bills"}
    AX = acct(db, s, names[next(iter(acct_but))], **acct_but)
    E = eo(db, s, "1", account_id=AX.id)
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _resync(db, s, E, V)
    # Then 2
    assert exc.value.status_code == status
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert reread(db, AccountInvoice, vid).account_id == s.A1.id


def test_eos_r_10__deleted_account_refused(db, s):
    """EOS-R-10 — a deleted account is refused with 400.
    Rules: _resync_draft_invoice R4, R4a."""
    AD = acct(db, s, "Old Vendor", is_deleted=True)
    E = eo(db, s, "1", account_id=AD.id)
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            _resync(db, s, E, V)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot assign invoice to deleted account"
    # Then 3
    assert reread(db, AccountInvoice, vid).account_id == s.A1.id


def test_eos_r_11__no_order_account_leaves_invoice(db, s):
    """EOS-R-11 — an order without an account leaves the invoice's account alone.
    Rules: _resync_draft_invoice R4."""
    E = eo(db, s, "1", account_id=None)
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    assert reread(db, AccountInvoice, vid).account_id == s.A1.id
    # Then 2
    assert "item_manually_updated" not in itypes(db, vid)


def test_eos_r_12__all_differ_one_header_update(db, s):
    """EOS-R-12 — due date, notes and account all differ: one header update.
    Rules: _resync_draft_invoice R2, R3, R4, R5."""
    E = eo(
        db,
        s,
        "1",
        account_id=s.A2.id,
        due_date=date(2026, 10, 15),
        description="Water bill",
    )
    V = inv(db, s, E, notes="Office rent", linked=True)
    commit_point(db)
    vid = V.id

    _resync(db, s, E, V)

    # Then 1
    v = reread(db, AccountInvoice, vid)
    assert v.account_id == s.A2.id
    assert v.due_date == date(2026, 10, 15)
    assert v.notes == "Water bill"
    # Then 2
    assert itypes(db, vid).count("item_manually_updated") == 1
    # Then 3
    assert itypes(db, vid).count("items_synced") == 1


def test_eos_r_13__resync_flushed_never_committed(db, s):
    """EOS-R-13 — the resync is flushed, never committed.
    Rules: _resync_draft_invoice Persistence (flush only)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    commit_point(db)
    vid = V.id

    with spies(db) as (cm, rb):
        _resync(db, s, E, V)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    db.rollback()
    # Then 3
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == vid) == 0


# --------------------------------------------------------------------------- #
# _sync_or_create_invoice
# --------------------------------------------------------------------------- #


def _sync(db, s, eo_id):
    svc._sync_or_create_invoice(db, eo_id=eo_id, workspace_id=s.W1.id, user_id=s.U2.id)


def test_eos_y_01__missing_order_404(db, s):
    """EOS-Y-01 — a missing order: 404.
    Rules: _sync_or_create_invoice Y1."""
    eo(db, s, "1")
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sync(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert counts(db) == before


def test_eos_y_02__linked_draft_resynced(db, s):
    """EOS-Y-02 — a linked draft is resynced; no second invoice.
    Rules: _sync_or_create_invoice Y2."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "999.00")
    commit_point(db)
    eid, vid = E.id, V.id

    _sync(db, s, eid)

    # Then 1
    assert [l.line_subtotal for l in LINES(db, vid)] == [Decimal("100.00")]
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == eid) == 1
    # Then 3
    assert types(db, eid) == []
    # Then 4
    assert notes(db) == []


def test_eos_y_03__linked_confirmed_nothing(db, s):
    """EOS-Y-03 — a linked confirmed invoice: nothing happens.
    Rules: _sync_or_create_invoice Y3."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    V = inv(db, s, E, confirmed=True, linked=True)
    VL = invl(db, s, V, 1, "999.00")
    before = commit_point(db)
    sV, sVL, sE = snap(db, V), snap(db, VL), snap(db, E)

    _sync(db, s, E.id)

    # Then 1
    assert snap(db, V) == sV
    # Then 2
    assert snap(db, VL) == sVL
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert counts(db) == before


def test_eos_y_04__linked_voided_nothing(db, s):
    """EOS-Y-04 — a linked voided invoice: nothing happens, no new draft.
    Rules: _sync_or_create_invoice Y3."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    V = inv(db, s, E, voided_inv=True, linked=True)
    before = commit_point(db)
    sV, sE = snap(db, V), snap(db, E)

    _sync(db, s, E.id)

    # Then 1
    assert snap(db, V) == sV
    # Then 2
    assert snap(db, E) == sE
    # Then 3
    assert counts(db) == before


def test_eos_y_05__linked_w2_invoice_nothing(db, s):
    """EOS-Y-05 — a linked W2 invoice: nothing happens, no new draft.
    Rules: _sync_or_create_invoice Y3; HR-16."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    Z = inv(db, s, E, ws="2", linked=True)
    ZL = invl(db, s, Z, 1, "999.00")
    before = commit_point(db)
    sZ, sZL, sE = snap(db, Z), snap(db, ZL), snap(db, E)

    _sync(db, s, E.id)

    # Then 1
    assert snap(db, Z) == sZ
    # Then 2
    assert snap(db, ZL) == sZL
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert counts(db) == before


def test_eos_y_06__not_met_nothing(db, s):
    """EOS-Y-06 — no invoice and approvals not met: nothing happens.
    Rules: _sync_or_create_invoice Y4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    before = commit_point(db)
    sE = snap(db, E)

    _sync(db, s, E.id)

    # Then 1
    assert snap(db, E) == sE
    # Then 2
    assert counts(db) == before


def test_eos_y_07__met_no_account_skip_event(db, s):
    """EOS-Y-07 — met but no account: one `invoice_autocreate_skipped` event, no invoice.
    Rules: _sync_or_create_invoice Y5."""
    E = eo(db, s, "1", account_id=None)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid = E.id

    _sync(db, s, eid)

    # Then 1
    assert types(db, eid) == ["invoice_autocreate_skipped"]
    # Then 2
    evs = EV(db, eid)
    assert evs[0].description == SKIPMSG
    assert evs[0].performed_by == s.U2.id
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0
    # Then 4
    assert notes(db) == []


def test_eos_y_08__skip_logged_every_call(db, s):
    """EOS-Y-08 — the skip is logged again on every call in that state.
    Rules: _sync_or_create_invoice Y5 (Q5)."""
    E = eo(db, s, "1", waived=True, account_id=None)
    line(db, E, 1, "100.00")
    commit_point(db)
    eid = E.id
    _sync(db, s, eid)

    _sync(db, s, eid)

    # Then 1
    assert types(db, eid) == ["invoice_autocreate_skipped", "invoice_autocreate_skipped"]
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0


def test_eos_y_09__met_no_lines_nothing(db, s):
    """EOS-Y-09 — met with an account but no lines: nothing happens.
    Rules: _sync_or_create_invoice Y6."""
    E = eo(db, s, "1", waived=True)
    before = commit_point(db)
    sE = snap(db, E)

    _sync(db, s, E.id)

    # Then 1
    assert snap(db, E) == sE
    # Then 2
    assert counts(db) == before


def test_eos_y_10__met_with_line_drafts_and_notifies(db, s):
    """EOS-Y-10 — met with an account and a line: a draft and the draft notice.
    Rules: _sync_or_create_invoice Y7."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U5, approved=True)
    commit_point(db)
    eid = E.id

    _sync(db, s, eid)

    # Then 1
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is not None
    inv_id = e.invoice_id
    # Then 2
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("100.00")
    assert v.order_id == eid
    # Then 3
    assert types(db, eid) == ["invoice_created"]
    # Then 4
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 5
    for n in notes(db):
        assert n.preview == DRAFTP
        assert n.source_type == "invoice"
        assert n.source_id == inv_id
        assert n.entity_id == eid


def test_eos_y_11__step_flushed_never_committed(db, s):
    """EOS-Y-11 — the step is flushed, never committed.
    Rules: _sync_or_create_invoice Persistence (flush only)."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    commit_point(db)
    eid, w1_id = E.id, s.W1.id

    with spies(db) as (cm, rb):
        _sync(db, s, eid)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    db.rollback()
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == w1_id) == 0


# --------------------------------------------------------------------------- #
# create_invoice_for_expense_order
# --------------------------------------------------------------------------- #


def _cif(db, s, eo_id):
    return svc.create_invoice_for_expense_order(
        db, eo_id=eo_id, workspace_id=s.W1.id, user_id=s.U2.id
    )


def test_eos_i_01__draft_by_hand_committed_notice(db, s):
    """EOS-I-01 — a met order gets its draft by hand, committed, with the draft notice.
    Rules: create_invoice_for_expense_order I5; TC1, TC2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    eid = E.id

    result = _cif(db, s, eid)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == eid
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    db.rollback()
    # Then 3
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_type == "payable"
    assert v.order_id == eid
    assert v.invoice_amount == Decimal("100.00")
    # Then 4
    assert types(db, eid) == ["invoice_created"]
    # Then 5
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 6
    for n in notes(db):
        assert n.preview == DRAFTP
        assert n.notification_type == "invoice_action"


def test_eos_i_02__draft_already_linked_409(db, s):
    """EOS-I-02 — a draft already linked: 409, the extra row is gone.
    Rules: create_invoice_for_expense_order I2; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    inv(db, s, E, linked=True)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Invoice already exists for this expense order"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, E) == sE
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_i_03__voided_invoice_linked_still_409(db, s):
    """EOS-I-03 — a voided invoice linked still counts: 409.
    Rules: create_invoice_for_expense_order I2 (any status)."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    inv(db, s, E, voided_inv=True, linked=True)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Invoice already exists for this expense order"
    # Then 4
    assert counts(db) == before


def test_eos_i_04__completed_order_409(db, s):
    """EOS-I-04 — a completed order is refused by the "already exists" check.
    Rules: create_invoice_for_expense_order I6, I2."""
    E = eo(db, s, "1", completed=True)
    line(db, E, 1, "100.00")
    V = inv(db, s, E, confirmed=True, linked=True)
    commit_point(db)
    sV = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Invoice already exists for this expense order"
    # Then 4
    assert snap(db, V) == sV


@xfail(3065)
def test_eos_i_05__voided_waived_refused(db, s):
    """EOS-I-05 — a voided waived order is refused; no draft is made.
    Rules: create_invoice_for_expense_order I3, Errors row I3 [BUG-3065]."""
    E = eo(db, s, "1", voided=True, waived=True)
    line(db, E, 1, "50.00")
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Expense order is voided"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, E) == sE
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


@xfail(3065)
def test_eos_i_06__voided_unmet_gets_voided_text(db, s):
    """EOS-I-06 — a voided order with unmet approvals gets the "voided" text, not the approvals one.
    Rules: create_invoice_for_expense_order I3, I4 [BUG-3065]."""
    E = eo(db, s, "1", voided=True)
    line(db, E, 1, "50.00")
    appr(db, s, E, s.U3)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Expense order is voided"
    # Then 3
    assert counts(db) == before


def test_eos_i_07__voided_unmet_never_drafted(db, s):
    """EOS-I-07 — a voided order with unmet approvals never gets a draft (today and after the fix).
    Rules: create_invoice_for_expense_order I3, I4."""
    E = eo(db, s, "1", voided=True)
    line(db, E, 1, "50.00")
    appr(db, s, E, s.U3)
    before = commit_point(db)
    sE = snap(db, E)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert snap(db, E) == sE
    # Then 4
    assert counts(db) == before


@xfail(3065)
def test_eos_i_08__voided_with_invoice_gets_400_not_409(db, s):
    """EOS-I-08 — a voided order with an invoice still linked gets the "voided" 400, not the 409.
    Rules: create_invoice_for_expense_order I3, I2 (check order I1, I3, I2, I4) [BUG-3065]."""
    Z = inv(db, s, None, voided_inv=True)
    E = eo(db, s, "1", voided=True, waived=True)
    link(db, E, Z)
    before = commit_point(db)
    sE, sZ = snap(db, E), snap(db, Z)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Expense order is voided"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert snap(db, Z) == sZ
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_i_09__approvals_not_met_400(db, s):
    """EOS-I-09 — approvals not met: 400, no draft.
    Rules: create_invoice_for_expense_order I4; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTMET
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_i_10__no_account_422(db, s):
    """EOS-I-10 — no account: 422, no draft.
    Rules: create_invoice_for_expense_order I5; _create_draft_invoice D1; TC3."""
    E = eo(db, s, "1", account_id=None)
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    before = commit_point(db)
    sE = snap(db, E)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, E.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Set an account on the expense order before creating an invoice"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, E) == sE
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_eos_i_11__no_lines_zero_draft_committed(db, s):
    """EOS-I-11 — no lines: a 0.00 draft with no lines is committed.
    Rules: create_invoice_for_expense_order I5."""
    E = eo(db, s, "1", waived=True)
    commit_point(db)

    result = _cif(db, s, E.id)

    # Then 1
    assert result.invoice_id is not None
    inv_id = result.invoice_id
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_amount == Decimal("0.00")
    assert v.invoice_status == "draft"
    # Then 3
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == inv_id) == 0


def test_eos_i_12__missing_order_404(db, s):
    """EOS-I-12 — a missing order: 404, the extra row is gone.
    Rules: create_invoice_for_expense_order I1; TC3."""
    eo(db, s, "1")
    commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_eos_i_13__w2_order_404(db, s):
    """EOS-I-13 — another workspace's order (W2): 404, no draft.
    Rules: create_invoice_for_expense_order I1; HR-16."""
    eo(db, s, "1")
    Z = eo(db, s, "9", ws="2", waived=True, account_id=s.A9.id)
    line(db, Z, 1, "100.00")
    before = commit_point(db)
    sZ = snap(db, Z)
    zid = Z.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cif(db, s, zid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 4
    assert snap(db, Z) == sZ
    # Then 5
    assert counts(db) == before


def test_eos_i_14__failing_commit_no_draft(db, s):
    """EOS-I-14 — a failing commit leaves no draft and no link.
    Rules: create_invoice_for_expense_order I5; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    before = commit_point(db)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _cif(db, s, eid)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, ExpenseOrder, eid).invoice_id is None
    # Then 4
    assert counts(db) == before


@xfail(3062)
def test_eos_i_15__order_read_with_row_lock(db, s):
    """EOS-I-15 — the order is read with a row lock before the checks.
    Rules: create_invoice_for_expense_order I1, I1a [BUG-3062]; HR-10."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    eid = E.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.create_invoice_for_expense_order(
            db, eo_id=eid, workspace_id=w1_id, user_id=u2_id
        )

    # Then 1
    assert result.id == eid
    # Then 2
    assert rec.first_read_lock("expense_orders")
    # Then 3
    assert rec.lock_clause("expense_orders")
    # Then 4
    assert rec.locks_before("expense_orders", "expense_order_approvers")


# --------------------------------------------------------------------------- #
# list_approvers
# --------------------------------------------------------------------------- #


def test_eos_la_01__approvers_with_profiles(db, s):
    """EOS-LA-01 — returns the order's approvers with profiles; neither commits nor rolls back.
    Rules: list_approvers A1; TC6."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3)
    appr(db, s, E, s.U4, approved=True)
    F = eo(db, s, "2")
    appr(db, s, F, s.U2)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_approvers(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert {(a.user_id, p.id) for a, p, _pos in result} == {
        (s.U3.id, s.U3.id),
        (s.U4.id, s.U4.id),
    }
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_eos_la_02__w2_order_404_no_rollback(db, s):
    """EOS-LA-02 — another workspace's order: 404, no rollback.
    Rules: list_approvers A1; TC6."""
    Z = eo(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)

    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.list_approvers(db, eo_id=zid, workspace_id=s.W1.id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# approval_summary_for
# --------------------------------------------------------------------------- #


def test_eos_as_01__one_of_two(db, s):
    """EOS-AS-01 — one of two approved: (1, 2, False); neither commits nor rolls back.
    Rules: approval_summary_for A2; TC6."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U4)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result == (1, 2, False)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_eos_as_02__both_approved(db, s):
    """EOS-AS-02 — both approved: (2, 2, True).
    Rules: approval_summary_for A2."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U4, approved=True)
    commit_point(db)

    result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result == (2, 2, True)


def test_eos_as_03__waived_met(db, s):
    """EOS-AS-03 — waived (required 0), no approvers: met.
    Rules: approval_summary_for A2."""
    E = eo(db, s, "1", waived=True)
    commit_point(db)

    result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result == (0, 0, True)


@xfail(755)
def test_eos_as_04__no_approvers_one_required(db, s):
    """EOS-AS-04 — no approvers and no requirement: 1 required, not met.
    Rules: approval_summary_for A2 [BUG-755] (manager pass-through)."""
    E = eo(db, s, "1")
    commit_point(db)

    result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert result == (0, 1, False)


def test_eos_as_05__w2_order_404_no_rollback(db, s):
    """EOS-AS-05 — another workspace's order: 404, no rollback.
    Rules: approval_summary_for A2; TC6."""
    Z = eo(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)

    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.approval_summary_for(db, eo_id=zid, workspace_id=s.W1.id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# add_approver
# --------------------------------------------------------------------------- #


def _add_appr(db, s, eo_id, user):
    return svc.add_approver(
        db, eo_id=eo_id, user_id=user.id, workspace_id=s.W1.id, assigned_by=s.U2.id
    )


def test_eos_aa_01__approver_added_committed(db, s):
    """EOS-AA-01 — the approver is added and committed.
    Rules: add_approver A3; TC1, TC2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    commit_point(db)
    eid = E.id

    result = _add_appr(db, s, eid, s.U4)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, ExpenseOrderApprover)
    assert result.user_id == s.U4.id
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, ExpenseOrderApprover, rid)
    assert row.expense_order_id == eid
    assert row.assigned_by == s.U2.id
    assert row.approved is False


def test_eos_aa_02__ready_order_assigned_and_reminded(db, s):
    """EOS-AA-02 — ready order: the new approver is assigned, the other pending approver is reminded.
    Rules: add_approver A4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3)
    commit_point(db)

    result = _add_appr(db, s, E.id, s.U4)

    # Then 1
    assert result.user_id == s.U4.id
    db.rollback()
    # Then 2
    assert sorted((n.recipient_user_id, n.notification_type) for n in notes(db)) == sorted(
        [(s.U4.id, "approval_assigned"), (s.U3.id, "approval_pending")]
    )


def test_eos_aa_03__not_ready_creator_gets_gap_notice(db, s):
    """EOS-AA-03 — order not ready: the new approver is assigned, the creator gets the gap notice.
    Rules: add_approver A4, A4a."""
    E = eo(db, s, "1")
    appr(db, s, E, s.U3)
    commit_point(db)

    result = _add_appr(db, s, E.id, s.U4)

    # Then 1
    assert result.user_id == s.U4.id
    db.rollback()
    # Then 2
    assert sorted((n.recipient_user_id, n.notification_type) for n in notes(db)) == sorted(
        [(s.U4.id, "approval_assigned"), (s.U1.id, "section_confirm")]
    )
    # Then 3
    sc = [n for n in notes(db) if n.notification_type == "section_confirm"]
    assert sc[0].preview == "Add at least one expense line before approvals can proceed"


def test_eos_aa_04__no_invoice_step(db, s):
    """EOS-AA-04 — no invoice step: a waived order with an account and a line still has no draft.
    Rules: add_approver A5."""
    E = eo(db, s, "1", waived=True)
    line(db, E, 1, "100.00")
    commit_point(db)
    eid = E.id

    result = _add_appr(db, s, eid, s.U4)

    # Then 1
    assert result.user_id == s.U4.id
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).invoice_id is None
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0
    # Then 4
    assert "invoice_autocreate_skipped" not in types(db, eid)
    assert "invoice_created" not in types(db, eid)


def test_eos_aa_05__duplicate_409(db, s):
    """EOS-AA-05 — a duplicate approver: 409 passes unchanged, the extra row is gone.
    Rules: add_approver A3; TC3."""
    E = eo(db, s, "1")
    P3 = appr(db, s, E, s.U3)
    before = commit_point(db)
    sP3 = snap(db, P3)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _add_appr(db, s, E.id, s.U3)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, P3) == sP3
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_aa_06__inactive_member_400(db, s):
    """EOS-AA-06 — an inactive member: 400 passes unchanged, nothing written.
    Rules: add_approver A3; TC3."""
    E = eo(db, s, "1")
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_appr(db, s, E.id, s.U5)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_eos_aa_07__failing_commit_no_approver(db, s):
    """EOS-AA-07 — a failing commit leaves no approver and no notification.
    Rules: add_approver A3; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    before = commit_point(db)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _add_appr(db, s, eid, s.U4)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert (
        count_where(db, ExpenseOrderApprover, ExpenseOrderApprover.expense_order_id == eid) == 0
    )
    # Then 4
    assert counts(db) == before


def test_eos_aa_08__failing_approver_notice_undoes_add(db, s):
    """EOS-AA-08 — a failing approver notification undoes the add.
    Rules: add_approver A3, A4; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    before = commit_point(db)
    eid = E.id
    x, x_id = mk_x(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_approver_notify(db) as rb:
            _add_appr(db, s, eid, s.U4)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert x not in db
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert (
        count_where(db, ExpenseOrderApprover, ExpenseOrderApprover.expense_order_id == eid) == 0
    )
    # Then 5
    assert counts(db) == before
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


# --------------------------------------------------------------------------- #
# remove_approver
# --------------------------------------------------------------------------- #


def _rm_appr(db, s, eo_id, user):
    return svc.remove_approver(
        db, eo_id=eo_id, user_id=user.id, workspace_id=s.W1.id, performed_by=s.U2.id
    )


def test_eos_ra_01__removed_committed_no_notice(db, s):
    """EOS-RA-01 — the approver is removed and committed; returns None; no notification.
    Rules: remove_approver A6, A8; Returns."""
    E = eo(db, s, "1")
    P3 = appr(db, s, E, s.U3)
    P4 = appr(db, s, E, s.U4)
    commit_point(db)
    sP3 = snap(db, P3)
    p4_id = P4.id

    result = _rm_appr(db, s, E.id, s.U4)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert gone(db, ExpenseOrderApprover, p4_id)
    # Then 3
    assert snap(db, P3) == sP3
    # Then 4
    assert notes(db) == []


@xfail(3066)
def test_eos_ra_02__removal_meets_approvals_drafts_invoice(db, s):
    """EOS-RA-02 — removing the last pending approver makes approvals met and drafts the invoice.
    Rules: remove_approver A7 [BUG-3066]."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    P4 = appr(db, s, E, s.U4)
    commit_point(db)
    eid, p4_id = E.id, P4.id

    result = _rm_appr(db, s, eid, s.U4)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert gone(db, ExpenseOrderApprover, p4_id)
    # Then 3
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is not None
    inv_id = e.invoice_id
    # Then 4
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("100.00")
    # Then 5
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 6
    for n in notes(db):
        assert n.preview == DRAFTP


def test_eos_ra_03__summary_met_after_removal(db, s):
    """EOS-RA-03 — after removing the pending approver the summary reads met (today and after the fix).
    Rules: remove_approver A6."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    appr(db, s, E, s.U3, approved=True)
    appr(db, s, E, s.U4)
    commit_point(db)
    eid = E.id

    result = _rm_appr(db, s, eid, s.U4)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert svc.approval_summary_for(db, eo_id=eid, workspace_id=s.W1.id) == (1, 1, True)


def test_eos_ra_04__not_an_approver_404(db, s):
    """EOS-RA-04 — not an approver: 404 passes unchanged, the extra row is gone.
    Rules: remove_approver A6; TC3."""
    E = eo(db, s, "1")
    P3 = appr(db, s, E, s.U3)
    commit_point(db)
    sP3 = snap(db, P3)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _rm_appr(db, s, E.id, s.U4)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Approver not found"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, P3) == sP3
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_ra_05__failing_commit_keeps_approver(db, s):
    """EOS-RA-05 — a failing commit keeps the approver.
    Rules: remove_approver A6; TC4."""
    E = eo(db, s, "1")
    P4 = appr(db, s, E, s.U4)
    commit_point(db)
    sP4 = snap(db, P4)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _rm_appr(db, s, eid, s.U4)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, P4) == sP4


# --------------------------------------------------------------------------- #
# approve_as_me
# --------------------------------------------------------------------------- #


def _approve(db, s, eo_id, user):
    return svc.approve_as_me(db, eo_id=eo_id, user_id=user.id, workspace_id=s.W1.id)


def test_eos_ap_01__approval_recorded_not_met_no_draft(db, s):
    """EOS-AP-01 — the approval is recorded and committed; one of two is not met, no draft.
    Rules: approve_as_me A9a, A9b; TC1, TC2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3)
    appr(db, s, E, s.U4)
    commit_point(db)
    eid, p3_id = E.id, P3.id

    result = _approve(db, s, eid, s.U3)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == p3_id
    db.rollback()
    # Then 3
    p3 = reread(db, ExpenseOrderApprover, p3_id)
    assert p3.approved is True
    assert p3.approved_at == NOW
    # Then 4
    assert reread(db, ExpenseOrder, eid).invoice_id is None
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0


def test_eos_ap_02__meeting_approval_drafts_invoice(db, s):
    """EOS-AP-02 — the approval that makes approvals met drafts the invoice and sends the notice.
    Rules: approve_as_me A9b; _sync_or_create_invoice Y7."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3)
    commit_point(db)
    eid, p3_id = E.id, P3.id

    result = _approve(db, s, eid, s.U3)

    # Then 1
    assert result.id == p3_id
    db.rollback()
    # Then 2
    e = reread(db, ExpenseOrder, eid)
    assert e.invoice_id is not None
    inv_id = e.invoice_id
    # Then 3
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("100.00")
    assert v.created_by == s.U3.id
    # Then 4
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 5
    for n in notes(db):
        assert n.preview == DRAFTP


def test_eos_ap_03__completed_order_invoice_alone(db, s):
    """EOS-AP-03 — approving a completed order leaves its confirmed invoice alone.
    Rules: approve_as_me A9b; _sync_or_create_invoice Y3."""
    E = eo(db, s, "1", completed=True)
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3)
    V = inv(db, s, E, confirmed=True, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    sV = snap(db, V)
    eid, p3_id = E.id, P3.id

    result = _approve(db, s, eid, s.U3)

    # Then 1
    assert result.id == p3_id
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrderApprover, p3_id).approved is True
    # Then 3
    assert snap(db, V) == sV
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == eid) == 1
    # Then 5
    assert notes(db) == []


def test_eos_ap_04__not_an_approver_403(db, s):
    """EOS-AP-04 — not an approver: 403 passes unchanged, the extra row is gone.
    Rules: approve_as_me A9a; TC3."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3)
    before = commit_point(db)
    sP3 = snap(db, P3)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _approve(db, s, E.id, s.U4)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, P3) == sP3
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_ap_05__failing_commit_unrecorded(db, s):
    """EOS-AP-05 — a failing commit leaves the approval unrecorded and no draft.
    Rules: approve_as_me A9a; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3)
    before = commit_point(db)
    sP3 = snap(db, P3)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _approve(db, s, eid, s.U3)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, P3) == sP3
    # Then 4
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# unapprove_as_me
# --------------------------------------------------------------------------- #


def _unapprove(db, s, eo_id, user):
    return svc.unapprove_as_me(db, eo_id=eo_id, user_id=user.id, workspace_id=s.W1.id)


def test_eos_ua_01__withdrawn_draft_stays(db, s):
    """EOS-UA-01 — the approval is withdrawn and committed; the draft stays; nobody told.
    Rules: unapprove_as_me A9 (Q4); TC1, TC2."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    V = inv(db, s, E, linked=True)
    invl(db, s, V, 1, "100.00")
    commit_point(db)
    sV = snap(db, V)
    eid, vid, p3_id = E.id, V.id, P3.id

    result = _unapprove(db, s, eid, s.U3)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == p3_id
    db.rollback()
    # Then 3
    p3 = reread(db, ExpenseOrderApprover, p3_id)
    assert p3.approved is False
    assert p3.approved_at is None
    # Then 4
    assert reread(db, ExpenseOrder, eid).invoice_id == vid
    # Then 5
    assert snap(db, V) == sV
    # Then 6
    assert notes(db) == []


def test_eos_ua_02__completed_order_400(db, s):
    """EOS-UA-02 — a completed order: 400 passes unchanged, the extra row is gone.
    Rules: unapprove_as_me A9; TC3."""
    E = eo(db, s, "1", completed=True)
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    inv(db, s, E, confirmed=True, linked=True)
    before = commit_point(db)
    sP3 = snap(db, P3)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _unapprove(db, s, E.id, s.U3)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot withdraw approval — order is complete"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert snap(db, P3) == sP3
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_eos_ua_03__failing_commit_keeps_approval(db, s):
    """EOS-UA-03 — a failing commit keeps the approval.
    Rules: unapprove_as_me A9; TC4."""
    E = eo(db, s, "1")
    line(db, E, 1, "100.00")
    P3 = appr(db, s, E, s.U3, approved=True)
    commit_point(db)
    sP3 = snap(db, P3)
    eid = E.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _unapprove(db, s, eid, s.U3)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, P3) == sP3


# --------------------------------------------------------------------------- #
# list_events
# --------------------------------------------------------------------------- #


def test_eos_n_01__events_newest_first(db, s):
    """EOS-N-01 — returns the order's events newest first; neither commits nor rolls back.
    Rules: list_events N1; TC6."""
    E = eo(db, s, "1")
    EA = ev(db, s, E, T1)
    EB = ev(db, s, E, T0)
    EC = ev(db, s, E, T2)
    F = eo(db, s, "2")
    ev(db, s, F, T2)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_events(db, eo_id=E.id, workspace_id=s.W1.id)

    # Then 1
    assert [e.id for e, _p in result] == [EC.id, EA.id, EB.id]
    # Then 2
    assert [p.id for _e, p in result] == [s.U1.id, s.U1.id, s.U1.id]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_eos_n_02__w2_order_404_no_rollback(db, s):
    """EOS-N-02 — another workspace's order: 404, no rollback.
    Rules: list_events N1; TC6."""
    Z = eo(db, s, "9", ws="2")
    ev(db, s, Z, T0)
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)

    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.list_events(db, eo_id=zid, workspace_id=s.W1.id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Expense order with ID {zid} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# create_expense_order_from_template
# --------------------------------------------------------------------------- #


def _from_tpl(db, s, tpl_id):
    return svc.create_expense_order_from_template(
        db,
        template_id=tpl_id,
        overrides=ExpenseOrderFromTemplateCreate(),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )


def test_eos_t_01__waiving_template_order_and_draft(db, s):
    """EOS-T-01 — a waiving template with an account and a line: order and draft committed, draft notice.
    Rules: create_expense_order_from_template T1, T2; TC1, TC2."""
    TPL = tpl(db, s, waiving=True)
    tplline(db, TPL, 1, "5000.00")
    commit_point(db)

    result = _from_tpl(db, s, TPL.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, ExpenseOrder)
    assert result.invoice_id is not None
    rid, inv_id = result.id, result.invoice_id
    db.rollback()
    # Then 3
    e = reread(db, ExpenseOrder, rid)
    assert e.required_approvals == 0
    assert e.account_id == s.A1.id
    assert e.created_by == s.U2.id
    # Then 4
    v = reread(db, AccountInvoice, inv_id)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("5000.00")
    assert v.order_id == rid
    assert v.created_by == s.U2.id
    # Then 5
    assert recips(db) == [s.U2.id]
    # Then 6
    assert notes(db)[0].preview == DRAFTP


def test_eos_t_02__waiving_no_account_skip_event(db, s):
    """EOS-T-02 — a waiving template without an account: the skip event, no invoice.
    Rules: create_expense_order_from_template T2; _sync_or_create_invoice Y5."""
    TPL = tpl(db, s, waiving=True, account_id=None)
    tplline(db, TPL, 1, "5000.00")
    commit_point(db)

    result = _from_tpl(db, s, TPL.id)

    # Then 1
    assert result.invoice_id is None
    rid = result.id
    db.rollback()
    # Then 2
    assert types(db, rid)[-1] == "invoice_autocreate_skipped"
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0
    # Then 4
    assert notes(db) == []


def test_eos_t_03__approval_template_default_approver(db, s):
    """EOS-T-03 — a template that needs approval, with a default approver: no invoice, no notification.
    Rules: create_expense_order_from_template T1, T2, T3."""
    TPL = tpl(db, s, default_approver_id=s.U3.id)
    tplline(db, TPL, 1, "5000.00")
    commit_point(db)

    result = _from_tpl(db, s, TPL.id)

    # Then 1
    assert result.invoice_id is None
    rid = result.id
    db.rollback()
    # Then 2
    rows = rows_where(db, ExpenseOrderApprover, ExpenseOrderApprover.expense_order_id == rid)
    assert {a.user_id for a in rows} == {s.U2.id, s.U3.id}
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 0
    # Then 4
    assert notes(db) == []
    # Then 5
    assert "invoice_autocreate_skipped" not in types(db, rid)


def test_eos_t_04__inactive_template_400(db, s):
    """EOS-T-04 — an inactive template: the manager's 400, the extra row is gone.
    Rules: create_expense_order_from_template T1; TC3."""
    TPL = tpl(db, s, waiving=True, is_active=False)
    tplline(db, TPL, 1, "5000.00")
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _from_tpl(db, s, TPL.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Template is inactive"
    # Then 4
    assert x not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_t_05__draft_refused_undoes_order(db, s):
    """EOS-T-05 — the draft step refusing the account undoes the whole new order.
    Rules: create_expense_order_from_template T2; _create_draft_invoice D4; TC3."""
    A3 = acct(db, s, "No Bills", allow_invoices=False)
    TPL = tpl(db, s, waiving=True, account_id=A3.id)
    tplline(db, TPL, 1, "5000.00")
    before = commit_point(db)
    w1_id = s.W1.id
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        _from_tpl(db, s, TPL.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert x not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert count_where(db, ExpenseOrder, ExpenseOrder.workspace_id == w1_id) == 0
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_eos_t_06__failing_commit_no_order(db, s):
    """EOS-T-06 — a failing commit leaves no order and no invoice.
    Rules: create_expense_order_from_template T1; TC4."""
    TPL = tpl(db, s, waiving=True)
    tplline(db, TPL, 1, "5000.00")
    before = commit_point(db)
    w1_id, tpl_id = s.W1.id, TPL.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _from_tpl(db, s, tpl_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, ExpenseOrder, ExpenseOrder.workspace_id == w1_id) == 0
    # Then 4
    assert counts(db) == before
