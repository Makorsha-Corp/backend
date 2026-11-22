"""Unit tests for app/services/calendar_service.py.

Implements tests/unit/services/calendar_service.cases.md (revision 6), one test
per card, in card order. Real Postgres session (`db` fixture), rolled back after
each test. Nothing is patched except what Conventions name: the `db.commit` /
`db.rollback` spies and the failing `db.query` of CAL-GE-16.

Every test builds the Standing rows (autouse fixture `st`). Card row names are
the lower-case names here (A1 -> a1, `W1.id` -> `st.w1.id`); `# Then N` marks the
checks of the card's Then line N. Row builders live on the `mk` fixture.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event

from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.enums import (
    MaintenanceTypeEnum,
    ProjectStatusEnum,
    ProjectVisibilityEnum,
    WorkOrderPriorityEnum,
    WorkOrderStatusEnum,
)
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.invoice_payment import InvoicePayment
from app.models.machine import Machine
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.models.production_batch import ProductionBatch
from app.models.production_line import ProductionLine
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.purchase_order import PurchaseOrder
from app.models.sales_delivery import SalesDelivery
from app.models.sales_order import SalesOrder
from app.models.status import Status
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.calendar import CalendarCategory, CalendarEventResponse
from app.services.calendar_service import (
    _date_in_range,
    _dt_to_date,
    _event_id,
    calendar_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = calendar_service

# Convention "CalendarCategory as CC" (revision 3 note: a card's `CC.sales` means
# `CC.SALES`). CC maps each lower-case value to its member, so the cards'
# spelling reads as written.
CC = SimpleNamespace(**{m.value: m for m in CalendarCategory})

START = date(2026, 5, 1)
END = date(2026, 5, 31)
PRE = date(2026, 4, 30)
POST = date(2026, 6, 1)
MID = date(2026, 5, 10)
FAR = date(2025, 1, 1)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
MISSING = 999999999


# Convention "XID(k)": an explicit row id, unique per test process
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, built in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def st(db):
    s = SimpleNamespace()
    s.w0 = make_workspace(db)
    s.w1 = make_workspace(db)
    s.w2 = make_workspace(db)
    s.u1 = make_profile(db)
    w0, w1, w2 = s.w0.id, s.w1.id, s.w2.id
    s.f0 = _add(db, Factory(workspace_id=w0, name="Factory Zero", abbreviation="F0"))
    s.wt0 = _add(db, WorkOrderType(workspace_id=w0, name="Repair"))
    s.ac0 = _add(db, Account(workspace_id=w0, name="Zero Co"))
    s.s0 = _add(db, Status(workspace_id=w0, name="Draft", comment="Stage"))
    s.l0 = _add(db, ProductionLine(workspace_id=w0, factory_id=s.f0.id, name="Zero Line"))
    s.m0 = _add(db, Machine(workspace_id=w0, factory_id=s.f0.id, name="Zero Press"))
    s.f1 =_add(db, Factory(workspace_id=w1, name="Factory One", abbreviation="F1"))
    s.fd = _add(db, Factory(workspace_id=w1, name="Old Plant", abbreviation="OP", is_deleted=True))
    s.fi = _add(db, Factory(workspace_id=w1, name="Idle Plant", abbreviation="IP", is_active=False))
    s.f9 = _add(db, Factory(workspace_id=w2, name="Factory Nine", abbreviation="F9"))
    s.wt1 = _add(db, WorkOrderType(workspace_id=w1, name="Repair"))
    s.wt9 = _add(db, WorkOrderType(workspace_id=w2, name="Repair"))
    s.ac1 = _add(db, Account(workspace_id=w1, name="Acme"))
    s.ac9 = _add(db, Account(workspace_id=w2, name="Far Co"))
    s.s1 = _add(db, Status(workspace_id=w1, name="Draft", comment="Stage"))
    s.s9 = _add(db, Status(workspace_id=w2, name="Draft", comment="Stage"))
    s.l1 = _add(db, ProductionLine(workspace_id=w1, factory_id=s.f1.id, name="Line One"))
    s.li = _add(db, ProductionLine(workspace_id=w1, factory_id=s.f1.id, name="Off Line", is_active=False))
    s.lfi = _add(db, ProductionLine(workspace_id=w1, factory_id=s.fi.id, name="Idle Line"))
    s.ld = _add(db, ProductionLine(workspace_id=w1, factory_id=s.fd.id, name="Lost Line"))
    s.l9 = _add(db, ProductionLine(workspace_id=w2, factory_id=s.f9.id, name="Far Line"))
    s.m1 = _add(db, Machine(workspace_id=w1, factory_id=s.f1.id, name="Press 1"))
    s.md = _add(db, Machine(workspace_id=w1, factory_id=s.f1.id, name="Press 4", is_active=False, is_deleted=True))
    s.mf = _add(db, Machine(workspace_id=w1, factory_id=s.fd.id, name="Lost Press"))
    s.m9 = _add(db, Machine(workspace_id=w2, factory_id=s.f9.id, name="Far Press"))
    b = Builder(db, s)
    s.sox = b.so("SO-X", order_date=FAR)
    s.sox9 = b.so("SO-X9", w2=True, order_date=FAR)
    s.inx = b.inv("INV-X", invoice_date=FAR)
    s.inx9 = b.inv("INV-X9", w2=True, invoice_date=FAR)
    s.sox0 = b.so("SO-X0", w0=True, order_date=FAR)
    s.inx0 = b.inv("INV-X0", w0=True, invoice_date=FAR)
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows. Every date column not named is None; "W2 x" is
# `w2=True`, "W0 x" is `w0=True`; keyword arguments are the columns listed
# after "but".
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, db, s):
        self.db = db
        self.s = s

    def _v(self, w2, w0, one, nine, zero):
        # "W2 x" / "W0 x": the W2 or W0 counterpart of each standing row
        return getattr(self.s, zero if w0 else nine if w2 else one).id

    def _mk(self, model, fields, but):
        fields.update(but)
        return _add(self.db, model(**fields))

    def wo(self, number, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(WorkOrder, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "work_order_number": number, "title": "Fix press",
            "factory_id": self._v(w2, w0, "f1", "f9", "f0"), "work_order_type_id": self._v(w2, w0, "wt1", "wt9", "wt0"),
            "created_by": s.u1.id, "planned_date": None, "end_date": None,
        }, but)

    def po(self, number, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(PurchaseOrder, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "po_number": number, "destination_type": "storage",
            "destination_id": s.f1.id, "subtotal": Decimal("0.00"), "total_amount": Decimal("10.50"),
            "current_status_id": self._v(w2, w0, "s1", "s9", "s0"), "created_by": s.u1.id, "description": "Steel order",
            "order_date": None, "expected_delivery_date": None, "actual_delivery_date": None,
        }, but)

    def eo(self, number, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(ExpenseOrder, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "expense_number": number, "expense_category": "other",
            "subtotal": Decimal("0.00"), "total_amount": Decimal("20.00"), "created_by": s.u1.id,
            "description": "Power bill", "due_date": None,
        }, but)

    def so(self, number, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(SalesOrder, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "sales_order_number": number,
            "account_id": self._v(w2, w0, "ac1", "ac9", "ac0"), "factory_id": self._v(w2, w0, "f1", "f9", "f0"),
            "total_amount": Decimal("30.00"), "current_status_id": self._v(w2, w0, "s1", "s9", "s0"),
            "created_by": s.u1.id, "description": "Chairs", "expected_delivery_date": None,
        }, but)

    def dl(self, number, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(SalesDelivery, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "sales_order_id": self._v(w2, w0, "sox", "sox9", "sox0"),
            "delivery_number": number, "delivery_status": "planned", "created_by": s.u1.id,
            "scheduled_date": None, "actual_delivery_date": None,
        }, but)

    def inv(self, number, *, w2=False, w0=False, **but):
        return self._mk(AccountInvoice, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "account_id": self._v(w2, w0, "ac1", "ac9", "ac0"),
            "invoice_number": number, "invoice_type": "payable", "invoice_status": "confirmed",
            "invoice_amount": Decimal("100.00"), "paid_amount": Decimal("0.00"), "payment_status": "unpaid",
            "allow_payments": True, "description": "May rent", "due_date": None,
        }, but)

    def pay(self, *, w2=False, w0=False, **but):
        s = self.s
        return self._mk(InvoicePayment, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "invoice_id": self._v(w2, w0, "inx", "inx9", "inx0"),
            "payment_amount": Decimal("40.00"), "payment_method": "cash", "created_by": s.u1.id,
        }, but)

    def batch(self, number, *, w2=False, w0=False, **but):
        return self._mk(ProductionBatch, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "batch_number": number,
            "production_line_id": self._v(w2, w0, "l1", "l9", "l0"), "status": "draft", "notes": "Run A",
        }, but)

    def proj(self, name, *, w2=False, w0=False, **but):
        return self._mk(Project, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "factory_id": self._v(w2, w0, "f1", "f9", "f0"), "name": name,
            "description": "Main", "start_date": None, "end_date": None, "deadline": None,
        }, but)

    def log(self, *, w2=False, w0=False, **but):
        return self._mk(MachineMaintenanceLog, {
            "workspace_id": self._v(w2, w0, "w1", "w2", "w0"), "machine_id": self._v(w2, w0, "m1", "m9", "m0"),
            "maintenance_type": MaintenanceTypeEnum.REPAIR, "summary": "Bearing change",
        }, but)

    # Access rows (OQ5 cards)
    def member(self, u, role, status="active"):
        return _add(self.db, WorkspaceMember(workspace_id=self.s.w1.id, user_id=u.id, role=role, status=status))

    def project_member(self, p, u):
        return _add(self.db, ProjectMember(workspace_id=self.s.w1.id, project_id=p.id, user_id=u.id))

    # "private proj" = proj, but this
    @property
    def private(self):
        return {"visibility": ProjectVisibilityEnum.INVITED_ONLY}

    # Closed states ("but deleted / voided / cancelled / gone")
    @property
    def deleted_wo(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.u1.id}

    @property
    def voided_po(self):  # also "voided eo"
        return {"voided": True, "void_note": "Void", "voided_at": T0, "voided_by": self.s.u1.id}

    @property
    def voided_inv(self):
        return {"invoice_status": "voided", "void_note": "Void", "paid_amount": Decimal("0.00"),
                "payment_status": "unpaid"}

    @property
    def voided_pay(self):
        return {"is_voided": True, "voided_at": T0, "voided_by": self.s.u1.id, "void_note": "manual void"}

    @property
    def cancelled_batch(self):
        return {"status": "cancelled", "updated_by": self.s.u1.id}

    @property
    def deleted_proj(self):
        return {"is_deleted": True, "deleted_at": T0, "deleted_by": self.s.u1.id}

    @property
    def gone_log(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.u1.id}


@pytest.fixture
def mk(db, st):
    return Builder(db, st)


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def keys(evs):
    return sorted((e.record_id, e.date_label) for e in evs)


def recs(evs):
    return sorted({e.record_id for e in evs})


def types_of(evs):
    return {e.source_type for e in evs}


def of(result, src):
    return [e for e in result if e.source_type == src]


# Convention "recorder": returns the statement list and the remover
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


# Convention "commit point"
def commit_point(db):
    db.commit()


def dt(*args):
    return datetime(*args)  # noqa: DTZ001  (naive, as the project columns)


# --------------------------------------------------------------------------- #
# _event_id
# --------------------------------------------------------------------------- #

# [claude] CAL-ID-01
def test_cal_id_01__the_id_is_source_record_field():
    """CAL-ID-01 — the id is source:record:field.
    Rules: `_event_id` R1"""
    result = _event_id("project", 5, "deadline")
    # Then 1
    assert result == "project:5:deadline"


# --------------------------------------------------------------------------- #
# _date_in_range
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(("value", "expected"), [
    pytest.param(MID, True, id="CAL-DR-01"),
    pytest.param(START, True, id="CAL-DR-02"),
    pytest.param(END, True, id="CAL-DR-03"),
    pytest.param(PRE, False, id="CAL-DR-04"),
    pytest.param(POST, False, id="CAL-DR-05"),
    pytest.param(None, False, id="CAL-DR-06"),
])
# [claude] CAL-DR-01 … CAL-DR-06
def test_cal_dr_01_06__date_in_range(value, expected):
    """CAL-DR-01 … DR-06 — inside, start, end in; the day before, the day after and None out.
    Rules: `_date_in_range` R1"""
    result = _date_in_range(value, START, END)
    # Then 1
    assert result is expected


# --------------------------------------------------------------------------- #
# _dt_to_date
# --------------------------------------------------------------------------- #

# [claude] CAL-DT-01
def test_cal_dt_01__a_datetime_gives_its_calendar_date():
    """CAL-DT-01 — a datetime gives its calendar date, the last microsecond included.
    Rules: `_dt_to_date` R1"""
    result = _dt_to_date(dt(2026, 5, 31, 23, 59, 59, 999999))
    # Then 1
    assert result == date(2026, 5, 31)
    # Then 2
    assert type(result) is date


# [claude] CAL-DT-02
def test_cal_dt_02__none_gives_none():
    """CAL-DT-02 — None gives None.
    Rules: `_dt_to_date` R1"""
    result = _dt_to_date(None)
    # Then 1
    assert result is None


# [claude] CAL-DT-03
def test_cal_dt_03__an_aware_datetime_keeps_its_own_calendar_date():
    """CAL-DT-03 — an aware datetime keeps its own calendar date (no conversion to UTC).
    Rules: `_dt_to_date` R1"""
    v = datetime(2026, 6, 1, 1, 30, tzinfo=timezone(timedelta(hours=6)))
    result = _dt_to_date(v)
    # Then 1
    assert result == date(2026, 6, 1)


# --------------------------------------------------------------------------- #
# CalendarService._category_allowed
# --------------------------------------------------------------------------- #

# [claude] CAL-CA-01
def test_cal_ca_01__no_filter_allows_every_category():
    """CAL-CA-01 — no filter allows every category.
    Rules: `_category_allowed` R1"""
    result = svc._category_allowed(CC.sales, None)
    # Then 1
    assert result is True


# [claude] CAL-CA-02
def test_cal_ca_02__a_listed_category_is_allowed():
    """CAL-CA-02 — a listed category is allowed.
    Rules: `_category_allowed` R1"""
    result = svc._category_allowed(CC.sales, {CC.purchase, CC.sales})
    # Then 1
    assert result is True


# [claude] CAL-CA-03
def test_cal_ca_03__a_category_not_listed_is_not_allowed():
    """CAL-CA-03 — a category not listed is not allowed.
    Rules: `_category_allowed` R1"""
    result = svc._category_allowed(CC.sales, {CC.purchase})
    # Then 1
    assert result is False


# [claude] CAL-CA-04
def test_cal_ca_04__an_empty_set_allows_nothing():
    """CAL-CA-04 — an empty set allows nothing.
    Rules: `_category_allowed` R1"""
    result = svc._category_allowed(CC.sales, set())
    # Then 1
    assert result is False


# --------------------------------------------------------------------------- #
# CalendarService._expand_date_fields
# --------------------------------------------------------------------------- #

# [claude] CAL-XF-01
def test_cal_xf_01__one_event_per_in_range_field_in_field_order():
    """CAL-XF-01 — one event per in-range field, in field order, every field set.
    Rules: `_expand_date_fields` R1, R3"""
    r = SimpleNamespace(id=42, x_date=date(2026, 5, 20), y_date=date(2026, 5, 5))
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects,
        date_fields=[("x_date", "X date"), ("y_date", "Y date")], title="T-1", subtitle="Sub", link="/t",
        start=START, end=END, meta={"k": 1},
    )
    # Then 1
    assert len(result) == 2
    # Then 2
    assert isinstance(result[0], CalendarEventResponse)
    # Then 3
    assert result[0].id == "thing:42:x_date"
    assert result[0].category == CC.projects
    assert result[0].source_type == "thing"
    assert result[0].record_id == 42
    # Then 4
    assert result[0].date == date(2026, 5, 20)
    assert result[0].date_label == "X date"
    # Then 5
    assert result[0].title == "T-1"
    assert result[0].subtitle == "Sub"
    assert result[0].link == "/t"
    assert result[0].meta == {"k": 1}
    # Then 6
    assert result[1].id == "thing:42:y_date"
    assert result[1].date == date(2026, 5, 5)
    assert result[1].date_label == "Y date"


# [claude] CAL-XF-02
def test_cal_xf_02__a_field_the_record_does_not_have_counts_as_none():
    """CAL-XF-02 — a field the record does not have counts as None.
    Rules: `_expand_date_fields` R1, R2"""
    r = SimpleNamespace(id=43, x_date=MID)
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects, date_fields=[("nope", "Nope"), ("x_date", "X date")],
        title="T-2", subtitle=None, link="/t", start=START, end=END,
    )
    # Then 1
    assert [e.date_label for e in result] == ["X date"]


# [claude] CAL-XF-03
def test_cal_xf_03__a_datetime_value_is_reduced_to_its_date():
    """CAL-XF-03 — a datetime value is reduced to its date.
    Rules: `_expand_date_fields` R1"""
    r = SimpleNamespace(id=44, x_date=dt(2026, 5, 31, 23, 30))
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")],
        title="T-3", subtitle=None, link="/t", start=START, end=END,
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].date == date(2026, 5, 31)


# [claude] CAL-XF-04
def test_cal_xf_04__none_and_out_of_range_give_no_event_both_edges_give_one():
    """CAL-XF-04 — None and out-of-range values give no event; both edges give one.
    Rules: `_expand_date_fields` R2; `_date_in_range` R1"""
    r = SimpleNamespace(id=45, a=PRE, b=START, c=END, d=POST, e=None)
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects,
        date_fields=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"), ("e", "E")],
        title="T-4", subtitle=None, link="/t", start=START, end=END,
    )
    # Then 1
    assert [e.date_label for e in result] == ["B", "C"]


# [claude] CAL-XF-05
def test_cal_xf_05__no_meta_gives_an_empty_dict():
    """CAL-XF-05 — no meta gives an empty dict.
    Rules: `_expand_date_fields` R3"""
    r = SimpleNamespace(id=46, x_date=MID)
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")],
        title="T-5", subtitle=None, link="/t", start=START, end=END,
    )
    # Then 1
    assert result[0].meta == {}
    # Then 2
    assert result[0].subtitle is None


# [claude] CAL-XF-06
def test_cal_xf_06__two_fields_on_the_same_day_give_two_events():
    """CAL-XF-06 — two fields on the same day give two events.
    Rules: `_expand_date_fields` R4"""
    r = SimpleNamespace(id=47, x_date=MID, y_date=MID)
    result = svc._expand_date_fields(
        record=r, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date"), ("y_date", "Y date")],
        title="T-6", subtitle=None, link="/t", start=START, end=END,
    )
    # Then 1
    assert [e.id for e in result] == ["thing:47:x_date", "thing:47:y_date"]


# [claude] CAL-XF-07
def test_cal_xf_07__a_title_that_is_not_a_string_is_refused():
    """CAL-XF-07 — a title that is not a string is refused.
    Rules: `_expand_date_fields` Errors"""
    r = SimpleNamespace(id=48, x_date=MID)
    # Then 1
    with pytest.raises(ValidationError):
        svc._expand_date_fields(
            record=r, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")],
            title=None, subtitle=None, link="/t", start=START, end=END,
        )


# --------------------------------------------------------------------------- #
# CalendarService.get_events
# --------------------------------------------------------------------------- #

ALL_TYPES = {"work_order", "purchase_order", "expense_order", "sales_order", "sales_delivery", "account_invoice",
             "invoice_payment", "production_batch", "project"}


def _one_of_each(mk):
    mk.wo("WO-1", planned_date=MID)
    mk.po("PO-1", order_date=MID)
    mk.eo("EXP-1", expense_date=MID)
    mk.so("SO-1", order_date=MID)
    mk.dl("SD-1", scheduled_date=MID)
    mk.inv("INV-1", invoice_date=MID)
    mk.pay(payment_date=MID)
    mk.batch("B-1", batch_date=MID)
    mk.proj("Refit", start_date=dt(2026, 5, 10, 9, 0))


# [claude] CAL-GE-01
def test_cal_ge_01__start_after_end_is_refused_before_anything_is_read(db, st, mk):
    """CAL-GE-01 — start after end is refused before anything is read.
    Rules: `get_events` R1; Errors row 1"""
    mk.inv("INV-1", invoice_date=MID)
    w1_id = st.w1.id
    stmts, stop = recorder(db)
    try:
        # Then 1
        with pytest.raises(ValueError) as exc:
            svc.get_events(db, workspace_id=w1_id, start=date(2026, 5, 2), end=date(2026, 5, 1))
    finally:
        stop()
    # Then 2
    assert str(exc.value) == "start must be on or before end"
    # Then 3
    assert stmts == []


# [claude] CAL-GE-02
def test_cal_ge_02__start_equal_to_end_is_a_one_day_range(db, st, mk):
    """CAL-GE-02 — start equal to end is a one-day range.
    Rules: `get_events` R1"""
    mk.inv("INV-1", invoice_date=date(2026, 5, 9))
    a2 = mk.inv("INV-2", invoice_date=MID)
    mk.inv("INV-3", invoice_date=date(2026, 5, 11))
    p = mk.proj("Refit", deadline=dt(2026, 5, 10, 23, 59, 59))
    result = svc.get_events(db, workspace_id=st.w1.id, start=MID, end=MID)
    # Then 1
    assert keys(of(result, "account_invoice")) == [(a2.id, "Invoice date")]
    # Then 2
    assert keys(of(result, "project")) == [(p.id, "Deadline")]
    # Then 3
    assert len(result) == 2


# [claude] CAL-GE-03
def test_cal_ge_03__both_edges_of_the_range_are_included(db, st, mk):
    """CAL-GE-03 — both edges of the range are included, the days outside are not.
    Rules: `get_events` R3, R5; `_collect_invoices` R1"""
    mk.inv("INV-1", invoice_date=PRE)
    a2 = mk.inv("INV-2", invoice_date=START)
    a3 = mk.inv("INV-3", invoice_date=END)
    mk.inv("INV-4", invoice_date=POST)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert keys(result) == [(a2.id, "Invoice date"), (a3.id, "Invoice date")]


# [claude] CAL-GE-04
def test_cal_ge_04__types_none_gives_every_category(db, st, mk):
    """CAL-GE-04 — types=None gives every category, sales orders and deliveries, invoices and payments.
    Rules: `get_events` R2, R3"""
    _one_of_each(mk)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=None)
    # Then 1
    assert types_of(result) == ALL_TYPES
    # Then 2
    assert len(result) == 9
    # Then 3
    assert {e.category for e in result} == {
        CC.work_orders, CC.purchase, CC.expense, CC.sales, CC.invoices, CC.production, CC.projects,
    }


# [claude] CAL-GE-05
def test_cal_ge_05__types_empty_gives_every_category_too(db, st, mk):
    """CAL-GE-05 — types=[] gives every category too.
    Rules: `get_events` R2"""
    _one_of_each(mk)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[])
    # Then 1
    assert types_of(result) == ALL_TYPES
    # Then 2
    assert len(result) == 9


# [claude] CAL-GE-06
def test_cal_ge_06__types_purchase_gives_purchase_orders_only(db, st, mk):
    """CAL-GE-06 — types=[purchase] gives purchase orders only.
    Rules: `get_events` R2"""
    mk.wo("WO-1", planned_date=MID)
    p = mk.po("PO-1", order_date=MID)
    mk.eo("EXP-1", expense_date=MID)
    mk.so("SO-1", order_date=MID)
    mk.inv("INV-1", invoice_date=MID)
    mk.proj("Refit", start_date=dt(2026, 5, 10, 9, 0))
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.purchase])
    # Then 1
    assert types_of(result) == {"purchase_order"}
    # Then 2
    assert keys(result) == [(p.id, "Order date")]


# [claude] CAL-GE-07
def test_cal_ge_07__types_sales_gives_sales_orders_and_deliveries_only(db, st, mk):
    """CAL-GE-07 — types=[sales] gives sales orders and deliveries only.
    Rules: `get_events` R2, R3"""
    mk.po("PO-1", order_date=MID)
    mk.so("SO-1", order_date=MID)
    mk.dl("SD-1", scheduled_date=MID)
    mk.inv("INV-1", invoice_date=MID)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.sales])
    # Then 1
    assert types_of(result) == {"sales_order", "sales_delivery"}
    # Then 2
    assert len(result) == 2


# [claude] CAL-GE-08
def test_cal_ge_08__types_invoices_gives_invoices_and_payments_only(db, st, mk):
    """CAL-GE-08 — types=[invoices] gives invoices and payments only.
    Rules: `get_events` R2, R3"""
    mk.so("SO-1", order_date=MID)
    mk.inv("INV-1", invoice_date=MID)
    mk.pay(payment_date=MID)
    mk.batch("B-1", batch_date=MID)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.invoices])
    # Then 1
    assert types_of(result) == {"account_invoice", "invoice_payment"}
    # Then 2
    assert len(result) == 2


# [claude] CAL-GE-09
def test_cal_ge_09__two_categories_one_listed_twice_each_event_once(db, st, mk):
    """CAL-GE-09 — two categories, one listed twice: each event once.
    Rules: `get_events` R2"""
    mk.wo("WO-1", planned_date=MID)
    mk.po("PO-1", order_date=MID)
    mk.eo("EXP-1", expense_date=MID)
    mk.proj("Refit", start_date=dt(2026, 5, 10, 9, 0))
    result = svc.get_events(
        db, workspace_id=st.w1.id, start=START, end=END, types=[CC.purchase, CC.projects, CC.purchase],
    )
    # Then 1
    assert types_of(result) == {"purchase_order", "project"}
    # Then 2
    assert len(result) == 2


# [claude] CAL-GE-10
def test_cal_ge_10__sorted_by_date_then_category_value_then_title(db, st, mk):
    """CAL-GE-10 — sorted by date, then category value as text, then title.
    Rules: `get_events` R4"""
    j = mk.proj("Alpha", start_date=dt(2026, 5, 10, 8, 0))
    i = mk.inv("INV-Z", invoice_date=MID)
    o = mk.wo("WO-A", planned_date=MID)
    p2 = mk.po("PO-B", order_date=MID)
    p1 = mk.po("PO-A", order_date=MID)
    e = mk.eo("EXP-Y", expense_date=MID)
    b = mk.batch("B-1", batch_date=MID)
    s = mk.so("SO-1", order_date=MID)
    z = mk.wo("WO-Z", planned_date=date(2026, 5, 9))
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert [(ev.source_type, ev.record_id) for ev in result] == [
        ("work_order", z.id), ("expense_order", e.id), ("account_invoice", i.id), ("production_batch", b.id),
        ("project", j.id), ("purchase_order", p1.id), ("purchase_order", p2.id), ("sales_order", s.id),
        ("work_order", o.id),
    ]


# [claude] CAL-GE-11
def test_cal_ge_11__one_records_two_events_on_the_same_day_keep_field_order(db, st, mk):
    """CAL-GE-11 — one record's two events on the same day keep field order.
    Rules: `get_events` R4; `_collect_invoices` R2"""
    mk.inv("INV-1", invoice_date=MID, due_date=MID)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert [e.date_label for e in result] == ["Invoice date", "Due date"]


# [claude] CAL-GE-12
def test_cal_ge_12__same_date_and_title_the_sales_order_comes_before_the_delivery(db, st, mk):
    """CAL-GE-12 — same date and title: the sales order comes before the delivery, whichever id is larger.
    Rules: `get_events` R4"""
    mk.dl("S-100", scheduled_date=MID, id=XID(1))
    mk.so("S-100", order_date=MID, id=XID(2))
    mk.so("S-200", order_date=date(2026, 5, 11), id=XID(3))
    mk.dl("S-200", scheduled_date=date(2026, 5, 11), id=XID(4))
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.sales])
    # Then 1
    assert [(e.source_type, e.record_id) for e in result] == [
        ("sales_order", XID(2)), ("sales_delivery", XID(1)), ("sales_order", XID(3)), ("sales_delivery", XID(4)),
    ]


# [claude] CAL-GE-13
def test_cal_ge_13__same_date_and_title_the_invoice_comes_before_the_payment(db, st, mk):
    """CAL-GE-13 — same date and title: the invoice comes before the payment, whichever id is larger.
    Rules: `get_events` R4"""
    mk.pay(payment_date=MID, id=XID(5))
    mk.inv(f"Payment #{XID(5)}", invoice_date=MID, id=XID(6))
    mk.inv(f"Payment #{XID(8)}", invoice_date=date(2026, 5, 11), id=XID(7))
    mk.pay(payment_date=date(2026, 5, 11), id=XID(8))
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.invoices])
    # Then 1
    assert [(e.source_type, e.record_id) for e in result] == [
        ("account_invoice", XID(6)), ("invoice_payment", XID(5)), ("account_invoice", XID(7)), ("invoice_payment", XID(8)),
    ]


# [claude] CAL-GE-14
def test_cal_ge_14__a_read_no_commit_no_rollback_pending_changes_stay_pending(db, st, mk):
    """CAL-GE-14 — a read: no commit, no rollback, the caller's pending changes stay pending.
    Rules: `get_events` R5; TC6 (`base_service.spec.md`)"""
    k = mk.inv("INV-1", invoice_date=MID)
    commit_point(db)
    k.description = "Edited"
    n = Account(workspace_id=st.w1.id, name="Pending")
    db.add(n)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert k in db.dirty
    # Then 2
    assert len(db.dirty) == 1
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert rb.call_count == 0
    # Then 7
    assert recs(result) == [k.id]


# [claude] CAL-GE-15
def test_cal_ge_15__nothing_in_range_for_this_workspace_gives_empty(db, st, mk):
    """CAL-GE-15 — nothing in range for this workspace gives [].
    Rules: `get_events` R5"""
    mk.inv("INV-1", invoice_date=FAR)
    mk.inv("INV-9", w2=True, invoice_date=MID)
    mk.proj("Far", w2=True, start_date=dt(2026, 5, 10, 9, 0))
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert result == []


# [claude] CAL-GE-16
def test_cal_ge_16__a_database_error_reaches_the_caller_unchanged(db, st):
    """CAL-GE-16 — a database error reaches the caller unchanged.
    Rules: `get_events` Errors row 2"""
    e = RuntimeError("db down")
    w1_id = st.w1.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "query", side_effect=e):
            svc.get_events(db, workspace_id=w1_id, start=START, end=END)
    assert exc.value is e


# [claude] CAL-GE-17
@pytest.mark.xfail(strict=True, reason="BUG-1805")
def test_cal_ge_17__maintenance_logs_on_both_edges_appear_under_maintenance(db, st, mk):
    """CAL-GE-17 — maintenance logs on both edges appear under maintenance; the days outside do not.
    Rules: `get_events` R6 [BUG-1805]"""
    mk.log(maintenance_date=PRE)
    a2 = mk.log(maintenance_date=START)
    a3 = mk.log(maintenance_date=END)
    mk.log(maintenance_date=POST)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.maintenance])
    # Then 1
    assert keys(result) == [(a2.id, "Maintenance date"), (a3.id, "Maintenance date")]
    # Then 2
    assert all(e.category == CC.maintenance for e in result)
    assert all(e.source_type == "machine_maintenance_log" for e in result)
    # Then 3
    ev2 = next(e for e in result if e.record_id == a2.id)
    assert ev2.id == f"machine_maintenance_log:{a2.id}:maintenance_date"
    assert ev2.date == START
    # Then 4
    ev3 = next(e for e in result if e.record_id == a3.id)
    assert ev3.id == f"machine_maintenance_log:{a3.id}:maintenance_date"
    assert ev3.date == END


# [claude] CAL-GE-18
@pytest.mark.xfail(strict=True, reason="BUG-1805")
def test_cal_ge_18__a_soft_deleted_log_gives_no_event_a_live_one_does(db, st, mk):
    """CAL-GE-18 — a soft-deleted log gives no event; a live one does (no filter).
    Rules: `get_events` R6 [BUG-1805]"""
    mk.log(maintenance_date=MID, **mk.gone_log)
    a = mk.log(maintenance_date=MID)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END)
    # Then 1
    assert recs(of(result, "machine_maintenance_log")) == [a.id]


# [claude] CAL-GE-19
@pytest.mark.xfail(strict=True, reason="BUG-1805")
def test_cal_ge_19__logs_of_a_deleted_machine_and_of_a_deleted_factorys_machine_still_appear(db, st, mk):
    """CAL-GE-19 — logs of a deleted machine and of a deleted factory's machine still appear.
    Rules: `get_events` R6 [BUG-1805]"""
    a1 = mk.log(maintenance_date=MID, machine_id=st.md.id)
    a2 = mk.log(maintenance_date=MID, machine_id=st.mf.id)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.maintenance])
    # Then 1
    assert recs(result) == sorted([a1.id, a2.id])


# [claude] CAL-GE-20
@pytest.mark.xfail(strict=True, reason="BUG-1805")
def test_cal_ge_20__the_other_workspaces_logs_never_appear(db, st, mk):
    """CAL-GE-20 — the other workspace's logs (W0 and W2), before and after, never appear.
    Rules: `get_events` R6 [BUG-1805]"""
    mk.log(w2=True, maintenance_date=MID)
    a = mk.log(maintenance_date=MID)
    mk.log(w2=True, maintenance_date=MID)
    mk.log(w0=True, maintenance_date=MID)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.maintenance])
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-GE-21
@pytest.mark.xfail(strict=True, reason="BUG-1805")
def test_cal_ge_21__a_log_linked_to_another_workspaces_machine_gives_no_event(db, st, mk):
    """CAL-GE-21 — a log of this workspace linked to another workspace's machine gives no event.
    Rules: `get_events` R6 [BUG-1805] (BUG-1101 shape)"""
    a = mk.log(maintenance_date=MID)
    mk.log(maintenance_date=MID, machine_id=st.m9.id)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.maintenance])
    # Then 1
    assert recs(result) == [a.id]


# --------------------------------------------------------------------------- #
# CalendarService._collect_work_orders
# --------------------------------------------------------------------------- #

# [claude] CAL-WO-01
def test_cal_wo_01__a_work_orders_two_dates_give_two_events_with_every_field(db, st, mk):
    """CAL-WO-01 — a work order's two dates give two events with every field.
    Rules: `_collect_work_orders` R1, R2"""
    o = mk.wo("WO-100", planned_date=MID, end_date=date(2026, 5, 20),
              status=WorkOrderStatusEnum.IN_PROGRESS.value, priority=WorkOrderPriorityEnum.MEDIUM)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0].id == f"work_order:{o.id}:planned_date"
    assert result[0].category == CC.work_orders
    assert result[0].source_type == "work_order"
    assert result[0].record_id == o.id
    # Then 3
    assert result[0].date == MID
    assert result[0].date_label == "Planned date"
    # Then 4
    assert result[0].title == "WO-100"
    assert result[0].subtitle == "Fix press"
    assert result[0].link == "/orders/work"
    # Then 5
    assert result[0].meta == {"status": "IN_PROGRESS", "priority": "MEDIUM"}
    # Then 6
    assert result[1].id == f"work_order:{o.id}:end_date"
    assert result[1].date == date(2026, 5, 20)
    assert result[1].date_label == "End date"


@pytest.mark.parametrize(("field", "label"), [
    pytest.param("planned_date", "Planned date", id="CAL-WO-02"),
    pytest.param("end_date", "End date", id="CAL-WO-03"),
])
# [claude] CAL-WO-02, CAL-WO-03
def test_cal_wo_02_03__date_both_edges_in_the_days_outside_out(db, st, mk, field, label):
    """CAL-WO-02 / WO-03 — planned_date / end_date: both edges in, the days outside out.
    Rules: `_collect_work_orders` R1, R2"""
    mk.wo("WO-1", **{field: PRE})
    a2 = mk.wo("WO-2", **{field: START})
    a3 = mk.wo("WO-3", **{field: END})
    mk.wo("WO-4", **{field: POST})
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, label), (a3.id, label)]


# [claude] CAL-WO-04
def test_cal_wo_04__one_date_in_and_one_out_gives_only_the_event_in_range(db, st, mk):
    """CAL-WO-04 — one date in and one out gives only the event in range.
    Rules: `_collect_work_orders` R1, R2; `_expand_date_fields` R2"""
    a1 = mk.wo("WO-1", planned_date=PRE, end_date=MID)
    a2 = mk.wo("WO-2", planned_date=MID, end_date=POST)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a1.id, "End date"), (a2.id, "Planned date")]


# [claude] CAL-WO-05
def test_cal_wo_05__the_other_workspaces_orders_never_appear(db, st, mk):
    """CAL-WO-05 — the other workspace's orders (W0 and W2), before and after, never appear.
    Rules: `_collect_work_orders` R1; `_category_allowed` R1"""
    mk.wo("WO-91", w2=True, planned_date=MID)
    a = mk.wo("WO-1", planned_date=MID)
    mk.wo("WO-92", w2=True, planned_date=MID)
    mk.wo("WO-90", w0=True, planned_date=MID)
    result = svc._collect_work_orders(db, st.w1.id, START, END, {CC.work_orders, CC.purchase})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-WO-06
def test_cal_wo_06__a_soft_deleted_work_order_never_appears(db, st, mk):
    """CAL-WO-06 — a soft-deleted work order never appears.
    Rules: `_collect_work_orders` R1"""
    mk.wo("WO-9", planned_date=MID, **mk.deleted_wo)
    a = mk.wo("WO-1", planned_date=MID)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-WO-07
def test_cal_wo_07__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-WO-07 — another category allowed: [] and no SQL sent.
    Rules: `_collect_work_orders` R1; `_category_allowed` R1"""
    mk.wo("WO-1", planned_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_work_orders(db, st.w1.id, START, END, {CC.purchase})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-OQ14-01
@pytest.mark.xfail(strict=True, reason="BUG-1876")
def test_cal_oq14_01__a_voided_work_order_gives_no_event(db, st, mk):
    """CAL-OQ14-01 — a VOIDED work order gives no event (OQ-14 answered).
    Rules: `_collect_work_orders` R3 [BUG-1876]"""
    mk.wo("WO-V", planned_date=MID, status=WorkOrderStatusEnum.VOIDED.value, void_note="Void",
          voided_at=T0, voided_by=st.u1.id)
    a = mk.wo("WO-A", planned_date=MID, status=WorkOrderStatusEnum.DRAFT.value)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-OQ14-02
def test_cal_oq14_02__draft_in_progress_and_completed_work_orders_are_listed(db, st, mk):
    """CAL-OQ14-02 — draft, in-progress and completed work orders are listed (OQ-14 answered).
    Rules: `_collect_work_orders` R3a"""
    a1 = mk.wo("WO-D", planned_date=MID, status=WorkOrderStatusEnum.DRAFT.value)
    a2 = mk.wo("WO-C", planned_date=MID, status=WorkOrderStatusEnum.COMPLETED.value, completed_at=T0)
    a3 = mk.wo("WO-P", planned_date=MID, status=WorkOrderStatusEnum.IN_PROGRESS.value)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id, a3.id]


# [claude] CAL-OQ15-01
@pytest.mark.xfail(strict=True, reason="BUG-1877")
def test_cal_oq15_01__a_work_order_of_a_soft_deleted_factory_gives_no_event(db, st, mk):
    """CAL-OQ15-01 — a work order of a soft-deleted factory gives no event (OQ-15 answered).
    Rules: `_collect_work_orders` R4 [BUG-1877]"""
    mk.wo("WO-F", planned_date=MID, factory_id=st.fd.id)
    a = mk.wo("WO-A", planned_date=MID)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-WO-08
def test_cal_wo_08__a_work_order_of_an_inactive_but_live_factory_still_appears(db, st, mk):
    """CAL-WO-08 — a work order of an inactive but live factory still appears.
    Rules: `_collect_work_orders` R4 (part that holds today)"""
    a1 = mk.wo("WO-I", planned_date=MID, factory_id=st.fi.id)
    a2 = mk.wo("WO-A", planned_date=MID)
    result = svc._collect_work_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# --------------------------------------------------------------------------- #
# CalendarService._collect_purchase_orders
# --------------------------------------------------------------------------- #

# [claude] CAL-PO-01
def test_cal_po_01__a_purchase_orders_three_dates_give_three_events_with_every_field(db, st, mk):
    """CAL-PO-01 — a purchase order's three dates give three events with every field.
    Rules: `_collect_purchase_orders` R1, R2"""
    o = mk.po("PO-100", order_date=MID, expected_delivery_date=date(2026, 5, 15),
              actual_delivery_date=date(2026, 5, 20), account_id=st.ac1.id)
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Order date", "Expected delivery", "Actual delivery"]
    # Then 2
    assert [e.date for e in result] == [MID, date(2026, 5, 15), date(2026, 5, 20)]
    # Then 3
    assert [e.id for e in result] == [
        f"purchase_order:{o.id}:order_date", f"purchase_order:{o.id}:expected_delivery_date",
        f"purchase_order:{o.id}:actual_delivery_date",
    ]
    # Then 4
    assert result[0].category == CC.purchase
    assert result[0].source_type == "purchase_order"
    assert result[0].record_id == o.id
    # Then 5
    assert result[0].title == "PO-100"
    assert result[0].subtitle == "Steel order"
    assert result[0].link == f"/orders/purchase?orderId={o.id}"
    # Then 6
    assert result[0].meta == {"total_amount": "10.50", "account_id": st.ac1.id, "current_status_id": st.s1.id}


# [claude] CAL-PO-02
def test_cal_po_02__no_account_meta_account_id_is_none(db, st, mk):
    """CAL-PO-02 — no account: meta account_id is None.
    Rules: `_collect_purchase_orders` R2"""
    mk.po("PO-101", order_date=MID)
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].meta["account_id"] is None


@pytest.mark.parametrize(("field", "label"), [
    pytest.param("order_date", "Order date", id="CAL-PO-03"),
    pytest.param("expected_delivery_date", "Expected delivery", id="CAL-PO-04"),
    pytest.param("actual_delivery_date", "Actual delivery", id="CAL-PO-05"),
])
# [claude] CAL-PO-03, CAL-PO-04, CAL-PO-05
def test_cal_po_03_05__date_both_edges_in_the_days_outside_out(db, st, mk, field, label):
    """CAL-PO-03 / PO-04 / PO-05 — order / expected / actual delivery date: both edges in, the days outside out.
    Rules: `_collect_purchase_orders` R1, R2"""
    mk.po("PO-1", **{field: PRE})
    a2 = mk.po("PO-2", **{field: START})
    a3 = mk.po("PO-3", **{field: END})
    mk.po("PO-4", **{field: POST})
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, label), (a3.id, label)]


# [claude] CAL-PO-06
def test_cal_po_06__a_voided_purchase_order_never_appears(db, st, mk):
    """CAL-PO-06 — a voided purchase order never appears; a live draft one does.
    Rules: `_collect_purchase_orders` R1"""
    mk.po("PO-9", order_date=MID, **mk.voided_po)
    a = mk.po("PO-1", order_date=MID)
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PO-07
def test_cal_po_07__the_other_workspaces_orders_never_appear(db, st, mk):
    """CAL-PO-07 — the other workspace's orders (W0 and W2), before and after, never appear.
    Rules: `_collect_purchase_orders` R1; `_category_allowed` R1"""
    mk.po("PO-91", w2=True, order_date=MID)
    a = mk.po("PO-1", order_date=MID)
    mk.po("PO-92", w2=True, order_date=MID)
    mk.po("PO-90", w0=True, order_date=MID, destination_id=st.f0.id)
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, {CC.purchase, CC.expense})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PO-08
def test_cal_po_08__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-PO-08 — another category allowed: [] and no SQL sent.
    Rules: `_collect_purchase_orders` R1; `_category_allowed` R1"""
    mk.po("PO-1", order_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_purchase_orders(db, st.w1.id, START, END, {CC.expense})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# --------------------------------------------------------------------------- #
# CalendarService._collect_expense_orders
# --------------------------------------------------------------------------- #

# [claude] CAL-EO-01
def test_cal_eo_01__an_expense_orders_two_dates_give_two_events_with_every_field(db, st, mk):
    """CAL-EO-01 — an expense order's two dates give two events with every field.
    Rules: `_collect_expense_orders` R1, R2"""
    o = mk.eo("EXP-100", expense_date=MID, due_date=date(2026, 5, 25))
    result = svc._collect_expense_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Expense date", "Due date"]
    # Then 2
    assert [e.date for e in result] == [MID, date(2026, 5, 25)]
    # Then 3
    assert [e.id for e in result] == [f"expense_order:{o.id}:expense_date", f"expense_order:{o.id}:due_date"]
    # Then 4
    assert result[0].category == CC.expense
    assert result[0].source_type == "expense_order"
    assert result[0].record_id == o.id
    # Then 5
    assert result[0].title == "EXP-100"
    assert result[0].subtitle == "Power bill"
    assert result[0].link == "/orders/expense"
    # Then 6
    assert result[0].meta == {"category": "other", "total_amount": "20.00"}


# [claude] CAL-EO-02
def test_cal_eo_02__expense_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-EO-02 — expense_date: both edges in, the days outside out.
    Rules: `_collect_expense_orders` R1, R2"""
    mk.eo("EXP-1", expense_date=PRE)
    a2 = mk.eo("EXP-2", expense_date=START)
    a3 = mk.eo("EXP-3", expense_date=END)
    mk.eo("EXP-4", expense_date=POST)
    result = svc._collect_expense_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Expense date"), (a3.id, "Expense date")]


# [claude] CAL-EO-03
def test_cal_eo_03__due_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-EO-03 — due_date: both edges in, the days outside out.
    Rules: `_collect_expense_orders` R1, R2"""
    mk.eo("EXP-1", expense_date=FAR, due_date=PRE)
    a2 = mk.eo("EXP-2", expense_date=FAR, due_date=START)
    a3 = mk.eo("EXP-3", expense_date=FAR, due_date=END)
    mk.eo("EXP-4", expense_date=FAR, due_date=POST)
    result = svc._collect_expense_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Due date"), (a3.id, "Due date")]


# [claude] CAL-EO-04
def test_cal_eo_04__a_voided_expense_order_never_appears(db, st, mk):
    """CAL-EO-04 — a voided expense order never appears.
    Rules: `_collect_expense_orders` R1"""
    mk.eo("EXP-9", expense_date=MID, **mk.voided_po)
    a = mk.eo("EXP-1", expense_date=MID)
    result = svc._collect_expense_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-EO-05
def test_cal_eo_05__the_other_workspaces_orders_never_appear(db, st, mk):
    """CAL-EO-05 — the other workspace's orders (W0 and W2), before and after, never appear.
    Rules: `_collect_expense_orders` R1; `_category_allowed` R1"""
    mk.eo("EXP-91", w2=True, expense_date=MID)
    a = mk.eo("EXP-1", expense_date=MID)
    mk.eo("EXP-92", w2=True, expense_date=MID)
    mk.eo("EXP-90", w0=True, expense_date=MID)
    result = svc._collect_expense_orders(db, st.w1.id, START, END, {CC.expense, CC.purchase})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-EO-06
def test_cal_eo_06__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-EO-06 — another category allowed: [] and no SQL sent.
    Rules: `_collect_expense_orders` R1; `_category_allowed` R1"""
    mk.eo("EXP-1", expense_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_expense_orders(db, st.w1.id, START, END, {CC.purchase})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# --------------------------------------------------------------------------- #
# CalendarService._collect_sales_orders
# --------------------------------------------------------------------------- #

# [claude] CAL-SO-01
def test_cal_so_01__a_sales_orders_two_dates_give_two_events_with_every_field(db, st, mk):
    """CAL-SO-01 — a sales order's two dates give two events with every field.
    Rules: `_collect_sales_orders` R1, R2"""
    o = mk.so("SO-100", order_date=MID, expected_delivery_date=date(2026, 5, 22))
    result = svc._collect_sales_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Order date", "Expected delivery"]
    # Then 2
    assert [e.date for e in result] == [MID, date(2026, 5, 22)]
    # Then 3
    assert [e.id for e in result] == [f"sales_order:{o.id}:order_date", f"sales_order:{o.id}:expected_delivery_date"]
    # Then 4
    assert result[0].category == CC.sales
    assert result[0].source_type == "sales_order"
    assert result[0].record_id == o.id
    # Then 5
    assert result[0].title == "SO-100"
    assert result[0].subtitle == "Chairs"
    assert result[0].link == "/sales/overview"
    # Then 6
    assert result[0].meta == {"total_amount": "30.00"}


# [claude] CAL-SO-02
def test_cal_so_02__order_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-SO-02 — order_date: both edges in, the days outside out.
    Rules: `_collect_sales_orders` R1, R2"""
    mk.so("SO-1", order_date=PRE)
    a2 = mk.so("SO-2", order_date=START)
    a3 = mk.so("SO-3", order_date=END)
    mk.so("SO-4", order_date=POST)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Order date"), (a3.id, "Order date")]


# [claude] CAL-SO-03
def test_cal_so_03__expected_delivery_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-SO-03 — expected_delivery_date: both edges in, the days outside out.
    Rules: `_collect_sales_orders` R1, R2"""
    mk.so("SO-1", order_date=FAR, expected_delivery_date=PRE)
    a2 = mk.so("SO-2", order_date=FAR, expected_delivery_date=START)
    a3 = mk.so("SO-3", order_date=FAR, expected_delivery_date=END)
    mk.so("SO-4", order_date=FAR, expected_delivery_date=POST)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Expected delivery"), (a3.id, "Expected delivery")]


# [claude] CAL-SO-04
def test_cal_so_04__the_other_workspaces_orders_never_appear(db, st, mk):
    """CAL-SO-04 — the other workspace's orders (W0 and W2), before and after, never appear.
    Rules: `_collect_sales_orders` R1; `_category_allowed` R1"""
    mk.so("SO-91", w2=True, order_date=MID)
    a = mk.so("SO-1", order_date=MID)
    mk.so("SO-92", w2=True, order_date=MID)
    mk.so("SO-90", w0=True, order_date=MID)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, {CC.sales, CC.invoices})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-SO-05
def test_cal_so_05__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-SO-05 — another category allowed: [] and no SQL sent.
    Rules: `_collect_sales_orders` R1; `_category_allowed` R1"""
    mk.so("SO-1", order_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, {CC.invoices})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-OQ15-02
@pytest.mark.xfail(strict=True, reason="BUG-1878")
def test_cal_oq15_02__a_sales_order_of_a_soft_deleted_factory_gives_no_event(db, st, mk):
    """CAL-OQ15-02 — a sales order of a soft-deleted factory gives no event (OQ-15 answered).
    Rules: `_collect_sales_orders` R3 [BUG-1878]"""
    mk.so("SO-F", order_date=MID, factory_id=st.fd.id)
    a = mk.so("SO-A", order_date=MID)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-SO-06
def test_cal_so_06__a_sales_order_of_an_inactive_but_live_factory_still_appears(db, st, mk):
    """CAL-SO-06 — a sales order of an inactive but live factory still appears.
    Rules: `_collect_sales_orders` R3 (part that holds today)"""
    a1 = mk.so("SO-I", order_date=MID, factory_id=st.fi.id)
    a2 = mk.so("SO-A", order_date=MID)
    result = svc._collect_sales_orders(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# --------------------------------------------------------------------------- #
# CalendarService._collect_sales_deliveries
# --------------------------------------------------------------------------- #

# [claude] CAL-SD-01
def test_cal_sd_01__a_deliverys_two_dates_give_two_events_with_every_field(db, st, mk):
    """CAL-SD-01 — a delivery's two dates give two events with every field.
    Rules: `_collect_sales_deliveries` R1, R2"""
    d = mk.dl("SD-100", scheduled_date=MID, actual_delivery_date=date(2026, 5, 12), delivery_status="delivered")
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Scheduled delivery", "Actual delivery"]
    # Then 2
    assert [e.date for e in result] == [MID, date(2026, 5, 12)]
    # Then 3
    assert [e.id for e in result] == [
        f"sales_delivery:{d.id}:scheduled_date", f"sales_delivery:{d.id}:actual_delivery_date",
    ]
    # Then 4
    assert result[0].category == CC.sales
    assert result[0].source_type == "sales_delivery"
    assert result[0].record_id == d.id
    # Then 5
    assert result[0].title == "SD-100"
    assert result[0].subtitle == f"Sales order #{st.sox.id}"
    assert result[0].link == "/sales/pipeline"
    # Then 6
    assert result[0].meta == {"delivery_status": "delivered"}


@pytest.mark.parametrize(("field", "label"), [
    pytest.param("scheduled_date", "Scheduled delivery", id="CAL-SD-02"),
    pytest.param("actual_delivery_date", "Actual delivery", id="CAL-SD-03"),
])
# [claude] CAL-SD-02, CAL-SD-03
def test_cal_sd_02_03__date_both_edges_in_the_days_outside_out(db, st, mk, field, label):
    """CAL-SD-02 / SD-03 — scheduled / actual delivery date: both edges in, the days outside out.
    Rules: `_collect_sales_deliveries` R1, R2"""
    mk.dl("SD-1", **{field: PRE})
    a2 = mk.dl("SD-2", **{field: START})
    a3 = mk.dl("SD-3", **{field: END})
    mk.dl("SD-4", **{field: POST})
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, label), (a3.id, label)]


# [claude] CAL-SD-04
def test_cal_sd_04__a_cancelled_delivery_never_appears(db, st, mk):
    """CAL-SD-04 — a cancelled delivery never appears; planned and delivered ones do.
    Rules: `_collect_sales_deliveries` R1"""
    mk.dl("SD-9", scheduled_date=MID, delivery_status="cancelled")
    a1 = mk.dl("SD-1", scheduled_date=MID)
    a2 = mk.dl("SD-2", scheduled_date=MID, delivery_status="delivered")
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# [claude] CAL-SD-05
def test_cal_sd_05__the_other_workspaces_deliveries_never_appear(db, st, mk):
    """CAL-SD-05 — the other workspace's deliveries (W0 and W2), before and after, never appear.
    Rules: `_collect_sales_deliveries` R1; `_category_allowed` R1"""
    mk.dl("SD-91", w2=True, scheduled_date=MID)
    a = mk.dl("SD-1", scheduled_date=MID)
    mk.dl("SD-92", w2=True, scheduled_date=MID)
    mk.dl("SD-90", w0=True, scheduled_date=MID)
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, {CC.sales})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-SD-06
def test_cal_sd_06__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-SD-06 — another category allowed: [] and no SQL sent.
    Rules: `_collect_sales_deliveries` R1; `_category_allowed` R1"""
    mk.dl("SD-1", scheduled_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, {CC.invoices})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-SD-07
def test_cal_sd_07__capital_cancelled_is_not_exactly_cancelled_that_delivery_is_listed(db, st, mk):
    """CAL-SD-07 — "Cancelled" is not exactly "cancelled": that delivery is listed.
    Rules: `_collect_sales_deliveries` R1"""
    mk.dl("SD-9", scheduled_date=MID, delivery_status="cancelled")
    a = mk.dl("SD-1", scheduled_date=MID, delivery_status="Cancelled")
    result = svc._collect_sales_deliveries(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# --------------------------------------------------------------------------- #
# CalendarService._collect_invoices
# --------------------------------------------------------------------------- #

# [claude] CAL-IN-01
def test_cal_in_01__an_invoices_two_dates_give_two_events_with_every_field(db, st, mk):
    """CAL-IN-01 — an invoice's two dates give two events with every field.
    Rules: `_collect_invoices` R1, R2, R3"""
    i = mk.inv("INV-100", invoice_date=MID, due_date=date(2026, 5, 28))
    result = svc._collect_invoices(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Invoice date", "Due date"]
    # Then 2
    assert [e.date for e in result] == [MID, date(2026, 5, 28)]
    # Then 3
    assert [e.id for e in result] == [f"account_invoice:{i.id}:invoice_date", f"account_invoice:{i.id}:due_date"]
    # Then 4
    assert result[0].category == CC.invoices
    assert result[0].source_type == "account_invoice"
    assert result[0].record_id == i.id
    # Then 5
    assert result[0].title == "INV-100"
    assert result[0].subtitle == "May rent"
    assert result[0].link == f"/accounts/{st.ac1.id}?invoiceId={i.id}"
    # Then 6
    assert result[0].meta == {
        "account_id": st.ac1.id, "invoice_type": "payable", "payment_status": "unpaid", "invoice_amount": "100.00",
    }


# [claude] CAL-IN-02
def test_cal_in_02__invoice_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-IN-02 — invoice_date: both edges in, the days outside out.
    Rules: `_collect_invoices` R1, R2"""
    mk.inv("INV-1", invoice_date=PRE)
    a2 = mk.inv("INV-2", invoice_date=START)
    a3 = mk.inv("INV-3", invoice_date=END)
    mk.inv("INV-4", invoice_date=POST)
    result = svc._collect_invoices(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Invoice date"), (a3.id, "Invoice date")]


# [claude] CAL-IN-03
def test_cal_in_03__due_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-IN-03 — due_date: both edges in, the days outside out.
    Rules: `_collect_invoices` R1, R2"""
    mk.inv("INV-1", invoice_date=FAR, due_date=PRE)
    a2 = mk.inv("INV-2", invoice_date=FAR, due_date=START)
    a3 = mk.inv("INV-3", invoice_date=FAR, due_date=END)
    mk.inv("INV-4", invoice_date=FAR, due_date=POST)
    result = svc._collect_invoices(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Due date"), (a3.id, "Due date")]


# [claude] CAL-IN-04
def test_cal_in_04__a_voided_invoice_never_appears(db, st, mk):
    """CAL-IN-04 — a voided invoice never appears; draft and confirmed ones do.
    Rules: `_collect_invoices` R1"""
    mk.inv("INV-9", invoice_date=MID, **mk.voided_inv)
    a1 = mk.inv("INV-1", invoice_date=MID, invoice_status="draft")
    a2 = mk.inv("INV-2", invoice_date=MID)
    result = svc._collect_invoices(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# [claude] CAL-IN-05
def test_cal_in_05__the_other_workspaces_invoices_never_appear(db, st, mk):
    """CAL-IN-05 — the other workspace's invoices (W0 and W2), before and after, never appear.
    Rules: `_collect_invoices` R1; `_category_allowed` R1"""
    mk.inv("INV-91", w2=True, invoice_date=MID)
    a = mk.inv("INV-1", invoice_date=MID)
    mk.inv("INV-92", w2=True, invoice_date=MID)
    mk.inv("INV-90", w0=True, invoice_date=MID)
    result = svc._collect_invoices(db, st.w1.id, START, END, {CC.invoices, CC.sales})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-IN-06
def test_cal_in_06__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-IN-06 — another category allowed: [] and no SQL sent.
    Rules: `_collect_invoices` R1; `_category_allowed` R1"""
    mk.inv("INV-1", invoice_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_invoices(db, st.w1.id, START, END, {CC.sales})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


@pytest.mark.parametrize("number", [
    pytest.param("", id="CAL-IN-07"),
    pytest.param(None, id="CAL-IN-08"),
])
# [claude] CAL-IN-07, CAL-IN-08
def test_cal_in_07_08__an_empty_or_missing_invoice_number_is_titled_invoice_id(db, st, mk, number):
    """CAL-IN-07 / IN-08 — an empty / no invoice number is titled Invoice #<id>.
    Rules: `_collect_invoices` R3"""
    i = mk.inv(number, invoice_date=MID)
    result = svc._collect_invoices(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].title == f"Invoice #{i.id}"


# --------------------------------------------------------------------------- #
# CalendarService._collect_invoice_payments
# --------------------------------------------------------------------------- #

# [claude] CAL-PY-01
def test_cal_py_01__a_payment_gives_one_event_with_every_field(db, st, mk):
    """CAL-PY-01 — a payment gives one event with every field, ids taken from its invoice.
    Rules: `_collect_invoice_payments` R1, R2"""
    y = mk.pay(payment_date=MID)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == f"invoice_payment:{y.id}:payment_date"
    assert result[0].category == CC.invoices
    assert result[0].source_type == "invoice_payment"
    assert result[0].record_id == y.id
    # Then 3
    assert result[0].date == MID
    assert result[0].date_label == "Payment date"
    # Then 4
    assert result[0].title == f"Payment #{y.id}"
    assert result[0].subtitle == f"Invoice #{st.inx.id}"
    # Then 5
    assert result[0].link == f"/accounts/{st.ac1.id}?invoiceId={st.inx.id}"
    # Then 6
    assert result[0].meta == {
        "invoice_id": st.inx.id, "account_id": st.ac1.id, "payment_amount": "40.00", "payment_method": "cash",
    }


# [claude] CAL-PY-02
def test_cal_py_02__no_payment_method_meta_payment_method_is_none(db, st, mk):
    """CAL-PY-02 — no payment method: meta payment_method is None.
    Rules: `_collect_invoice_payments` R2"""
    mk.pay(payment_date=MID, payment_method=None)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].meta["payment_method"] is None


# [claude] CAL-PY-03
def test_cal_py_03__payment_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-PY-03 — payment_date: both edges in, the days outside out.
    Rules: `_collect_invoice_payments` R1"""
    mk.pay(payment_date=PRE)
    a2 = mk.pay(payment_date=START)
    a3 = mk.pay(payment_date=END)
    mk.pay(payment_date=POST)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Payment date"), (a3.id, "Payment date")]


# [claude] CAL-PY-04
def test_cal_py_04__a_voided_payment_never_appears(db, st, mk):
    """CAL-PY-04 — a voided payment never appears.
    Rules: `_collect_invoice_payments` R1"""
    mk.pay(payment_date=MID, **mk.voided_pay)
    a = mk.pay(payment_date=MID)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PY-05
def test_cal_py_05__the_invoices_own_status_is_not_looked_at(db, st, mk):
    """CAL-PY-05 — the invoice's own status is not looked at.
    Rules: `_collect_invoice_payments` R1"""
    vi = mk.inv("INV-V", invoice_date=FAR, **mk.voided_inv)
    y = mk.pay(payment_date=MID, invoice_id=vi.id)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [y.id]
    # Then 2
    assert result[0].meta["invoice_id"] == vi.id


# [claude] CAL-PY-06
def test_cal_py_06__the_other_workspaces_payments_never_appear(db, st, mk):
    """CAL-PY-06 — the other workspace's payments (W0 and W2), before and after, never appear.
    Rules: `_collect_invoice_payments` R1 (the payment's own workspace decides); `_category_allowed` R1"""
    mk.pay(w2=True, payment_date=MID)
    a = mk.pay(payment_date=MID)
    mk.pay(w2=True, payment_date=MID)
    mk.pay(w0=True, payment_date=MID)
    mk.pay(w2=True, payment_date=MID, invoice_id=st.inx.id)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, {CC.invoices})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PY-07
def test_cal_py_07__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-PY-07 — another category allowed: [] and no SQL sent.
    Rules: `_collect_invoice_payments` R1; `_category_allowed` R1"""
    mk.pay(payment_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, {CC.sales})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-PY-08
@pytest.mark.xfail(strict=True, reason="BUG-1801")
def test_cal_py_08__a_payment_linked_to_another_workspaces_invoice_gives_no_event(db, st, mk):
    """CAL-PY-08 — a payment linked to another workspace's invoice gives no event.
    Rules: `_collect_invoice_payments` R3 [BUG-1801]"""
    a = mk.pay(payment_date=MID)
    mk.pay(payment_date=MID, invoice_id=st.inx9.id)
    result = svc._collect_invoice_payments(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]
    # Then 2
    assert all(e.meta["invoice_id"] != st.inx9.id for e in result)
    # Then 3
    assert all(e.meta["account_id"] != st.ac9.id for e in result)


# --------------------------------------------------------------------------- #
# CalendarService._collect_production_batches
# --------------------------------------------------------------------------- #

# [claude] CAL-PB-01
def test_cal_pb_01__a_batch_gives_one_event_with_every_field(db, st, mk):
    """CAL-PB-01 — a batch gives one event with every field.
    Rules: `_collect_production_batches` R1"""
    b = mk.batch("BATCH-2026-014", batch_date=MID, status="in_progress")
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == f"production_batch:{b.id}:batch_date"
    assert result[0].category == CC.production
    assert result[0].source_type == "production_batch"
    assert result[0].record_id == b.id
    # Then 3
    assert result[0].date == MID
    assert result[0].date_label == "Batch date"
    # Then 4
    assert result[0].title == "BATCH-2026-014"
    assert result[0].subtitle == "Run A"
    assert result[0].link == "/production"
    # Then 5
    assert result[0].meta == {"status": "in_progress"}


# [claude] CAL-PB-02
def test_cal_pb_02__batch_date_both_edges_in_the_days_outside_out(db, st, mk):
    """CAL-PB-02 — batch_date: both edges in, the days outside out.
    Rules: `_collect_production_batches` R1"""
    mk.batch("B-1", batch_date=PRE)
    a2 = mk.batch("B-2", batch_date=START)
    a3 = mk.batch("B-3", batch_date=END)
    mk.batch("B-4", batch_date=POST)
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, "Batch date"), (a3.id, "Batch date")]


# [claude] CAL-PB-03
def test_cal_pb_03__a_cancelled_batch_never_appears(db, st, mk):
    """CAL-PB-03 — a cancelled batch never appears; draft and in-progress ones do.
    Rules: `_collect_production_batches` R1"""
    mk.batch("B-9", batch_date=MID, **mk.cancelled_batch)
    a1 = mk.batch("B-1", batch_date=MID)
    a2 = mk.batch("B-2", batch_date=MID, status="in_progress")
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# [claude] CAL-PB-04
def test_cal_pb_04__batches_of_an_inactive_line_and_of_an_inactive_factorys_line_still_appear(db, st, mk):
    """CAL-PB-04 — batches of an inactive line and of an inactive factory's line still appear.
    Rules: `_collect_production_batches` R2 (part that holds today)"""
    a1 = mk.batch("B-1", batch_date=MID, production_line_id=st.li.id)
    a2 = mk.batch("B-2", batch_date=MID, production_line_id=st.lfi.id)
    a3 = mk.batch("B-3", batch_date=MID)
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id, a3.id]


# [claude] CAL-PB-05
def test_cal_pb_05__the_other_workspaces_batches_never_appear(db, st, mk):
    """CAL-PB-05 — the other workspace's batches (W0 and W2), before and after, never appear.
    Rules: `_collect_production_batches` R1; `_category_allowed` R1"""
    mk.batch("B-91", w2=True, batch_date=MID)
    a = mk.batch("B-1", batch_date=MID)
    mk.batch("B-92", w2=True, batch_date=MID)
    mk.batch("B-90", w0=True, batch_date=MID)
    result = svc._collect_production_batches(db, st.w1.id, START, END, {CC.production})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PB-06
def test_cal_pb_06__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-PB-06 — another category allowed: [] and no SQL sent.
    Rules: `_collect_production_batches` R1; `_category_allowed` R1"""
    mk.batch("B-1", batch_date=MID)
    stmts, stop = recorder(db)
    result = svc._collect_production_batches(db, st.w1.id, START, END, {CC.projects})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-PB-07
@pytest.mark.xfail(strict=True, reason="BUG-1807")
def test_cal_pb_07__a_batch_whose_lines_factory_is_soft_deleted_gives_no_event(db, st, mk):
    """CAL-PB-07 — a batch whose line's factory is soft-deleted gives no event.
    Rules: `_collect_production_batches` R2 [BUG-1807]"""
    mk.batch("B-9", batch_date=MID, production_line_id=st.ld.id)
    a = mk.batch("B-1", batch_date=MID)
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PB-08
def test_cal_pb_08__capital_cancelled_is_not_exactly_cancelled_that_batch_is_listed(db, st, mk):
    """CAL-PB-08 — "Cancelled" is not exactly "cancelled": that batch is listed.
    Rules: `_collect_production_batches` R1"""
    mk.batch("B-9", batch_date=MID, **mk.cancelled_batch)
    a = mk.batch("B-1", batch_date=MID, status="Cancelled")
    result = svc._collect_production_batches(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# --------------------------------------------------------------------------- #
# CalendarService._collect_projects
# --------------------------------------------------------------------------- #

# [claude] CAL-PJ-01
def test_cal_pj_01__a_projects_three_dates_give_three_events_with_every_field(db, st, mk):
    """CAL-PJ-01 — a project's three dates give three events with every field.
    Rules: `_collect_projects` R1, R4, R5"""
    p = mk.proj("Line 3 refit", start_date=dt(2026, 5, 2, 8, 0), end_date=dt(2026, 5, 20, 17, 0),
                deadline=dt(2026, 5, 25, 12, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert [e.date_label for e in result] == ["Start date", "End date", "Deadline"]
    # Then 2
    assert [e.date for e in result] == [date(2026, 5, 2), date(2026, 5, 20), date(2026, 5, 25)]
    # Then 3
    assert [e.id for e in result] == [f"project:{p.id}:start_date", f"project:{p.id}:end_date", f"project:{p.id}:deadline"]
    # Then 4
    assert result[0].category == CC.projects
    assert result[0].source_type == "project"
    assert result[0].record_id == p.id
    # Then 5
    assert result[0].title == "Line 3 refit"
    assert result[0].subtitle == "Main"
    assert result[0].link == "/project"
    # Then 6
    assert result[0].meta == {"status": "PLANNING"}


@pytest.mark.parametrize(("field", "label"), [
    pytest.param("start_date", "Start date", id="CAL-PJ-02"),
    pytest.param("end_date", "End date", id="CAL-PJ-03"),
    pytest.param("deadline", "Deadline", id="CAL-PJ-04"),
])
# [claude] CAL-PJ-02, CAL-PJ-03, CAL-PJ-04
def test_cal_pj_02_04__any_time_on_an_edge_day_is_in_the_instants_outside_are_out(db, st, mk, field, label):
    """CAL-PJ-02 / PJ-03 / PJ-04 — start_date / end_date / deadline: any time on an edge day is in, the instants
    outside are out.
    Rules: `_collect_projects` R1, R4"""
    mk.proj("P1", **{field: dt(2026, 4, 30, 23, 59, 59, 999999)})
    a2 = mk.proj("P2", **{field: dt(2026, 5, 1, 0, 0)})
    a3 = mk.proj("P3", **{field: dt(2026, 5, 31, 23, 30)})
    a4 = mk.proj("P4", **{field: dt(2026, 5, 31, 23, 59, 59, 999999)})
    mk.proj("P5", **{field: dt(2026, 6, 1, 0, 0)})
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert keys(result) == [(a2.id, label), (a3.id, label), (a4.id, label)]
    # Then 2
    assert {e.record_id: e.date for e in result} == {a2.id: START, a3.id: END, a4.id: END}


# [claude] CAL-PJ-05
def test_cal_pj_05__subtitle_120_characters_kept_whole_121_cut_to_120(db, st, mk):
    """CAL-PJ-05 — subtitle: 120 characters kept whole, 121 cut to 120.
    Rules: `_collect_projects` R5"""
    a1 = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0), description="x" * 120)
    a2 = mk.proj("P2", start_date=dt(2026, 5, 10, 9, 0), description="x" * 120 + "Y")
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert {e.record_id: e.subtitle for e in result} == {a1.id: "x" * 120, a2.id: "x" * 120}


# [claude] CAL-PJ-06
def test_cal_pj_06__an_empty_description_gives_no_subtitle(db, st, mk):
    """CAL-PJ-06 — an empty description gives no subtitle.
    Rules: `_collect_projects` R5"""
    mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0), description="")
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].subtitle is None


# [claude] CAL-PJ-07
def test_cal_pj_07__the_other_workspaces_projects_never_appear(db, st, mk):
    """CAL-PJ-07 — the other workspace's projects (W0 and W2), before and after, never appear.
    Rules: `_collect_projects` R1; `_category_allowed` R1"""
    mk.proj("Far 1", w2=True, start_date=dt(2026, 5, 10, 9, 0))
    a = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0))
    mk.proj("Far 2", w2=True, start_date=dt(2026, 5, 10, 9, 0))
    mk.proj("Zero 1", w0=True, start_date=dt(2026, 5, 10, 9, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, {CC.projects, CC.production})
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PJ-08
def test_cal_pj_08__another_category_allowed_empty_and_no_sql_sent(db, st, mk):
    """CAL-PJ-08 — another category allowed: [] and no SQL sent.
    Rules: `_collect_projects` R1; `_category_allowed` R1"""
    mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0))
    stmts, stop = recorder(db)
    result = svc._collect_projects(db, st.w1.id, START, END, {CC.production})
    stop()
    # Then 1
    assert result == []
    # Then 2
    assert stmts == []


# [claude] CAL-PJ-09
def test_cal_pj_09__a_project_of_an_inactive_but_live_factory_still_appears(db, st, mk):
    """CAL-PJ-09 — a project of an inactive but live factory still appears.
    Rules: `_collect_projects` R3 (part that holds today)"""
    a1 = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0), factory_id=st.fi.id)
    a2 = mk.proj("P2", start_date=dt(2026, 5, 10, 9, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id]


# [claude] CAL-PJ-10
@pytest.mark.xfail(strict=True, reason="BUG-1800")
def test_cal_pj_10__a_soft_deleted_project_gives_no_event(db, st, mk):
    """CAL-PJ-10 — a soft-deleted project gives no event.
    Rules: `_collect_projects` R2 [BUG-1800]"""
    mk.proj("Gone", start_date=dt(2026, 5, 10, 9, 0), **mk.deleted_proj)
    a = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PJ-11
@pytest.mark.xfail(strict=True, reason="BUG-1806")
def test_cal_pj_11__a_project_of_a_soft_deleted_factory_gives_no_event(db, st, mk):
    """CAL-PJ-11 — a project of a soft-deleted factory gives no event.
    Rules: `_collect_projects` R3 [BUG-1806]"""
    mk.proj("Lost", start_date=dt(2026, 5, 10, 9, 0), factory_id=st.fd.id)
    a = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a.id]


# [claude] CAL-PJ-12
def test_cal_pj_12__every_project_status_is_listed_meta_status_is_its_value_text(db, st, mk):
    """CAL-PJ-12 — every project status is listed, meta.status is its value text.
    Rules: `_collect_projects` R1, R4"""
    a1 = mk.proj("P1", start_date=dt(2026, 5, 10, 9, 0), status=ProjectStatusEnum.IN_PROGRESS)
    a2 = mk.proj("P2", start_date=dt(2026, 5, 10, 9, 0), status=ProjectStatusEnum.COMPLETED)
    a3 = mk.proj("P3", start_date=dt(2026, 5, 10, 9, 0), status=ProjectStatusEnum.ON_HOLD)
    a4 = mk.proj("P4", start_date=dt(2026, 5, 10, 9, 0), status=ProjectStatusEnum.CANCELLED)
    a5 = mk.proj("P5", start_date=dt(2026, 5, 10, 9, 0))
    result = svc._collect_projects(db, st.w1.id, START, END, None)
    # Then 1
    assert recs(result) == [a1.id, a2.id, a3.id, a4.id, a5.id]
    # Then 2
    assert {e.record_id: e.meta["status"] for e in result} == {
        a1.id: "IN_PROGRESS", a2.id: "COMPLETED", a3.id: "ON_HOLD", a4.id: "CANCELLED", a5.id: "PLANNING",
    }


# OQ5 cards: `get_events` has no `user_id` today, so the When call raises
# TypeError before Then 1 can be checked (the cards' "Fails today on").
# `raises=TypeError` pins the xfail to that cause; any other error fails.
BUG_1869 = pytest.mark.xfail(strict=True, raises=TypeError, reason="BUG-1869")
SECRET_AT = dt(2026, 5, 10, 9, 0)


# [claude] CAL-OQ5-01
@BUG_1869
def test_cal_oq5_01__a_member_who_may_not_open_a_private_project_does_not_see_it(db, st, mk):
    """CAL-OQ5-01 — a member who may not open a private project does not see it (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == [pw.id]


# [claude] CAL-OQ5-02
@BUG_1869
def test_cal_oq5_02__the_workspace_owner_sees_a_private_project(db, st, mk):
    """CAL-OQ5-02 — the workspace owner sees a private project.
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    st.w1.owner_user_id = ux.id
    db.flush()
    pv = mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == sorted([pv.id, pw.id])


@pytest.mark.parametrize("role", [
    pytest.param("owner", id="CAL-OQ5-03"),
    pytest.param("ground-team-manager", id="CAL-OQ5-04"),
])
# [claude] CAL-OQ5-03, CAL-OQ5-04
@BUG_1869
def test_cal_oq5_03_04__an_active_privileged_member_sees_a_private_project(db, st, mk, role):
    """CAL-OQ5-03 / OQ5-04 — an active member with role owner / ground-team-manager sees a private project.
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, role)
    pv = mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == sorted([pv.id, pw.id])


# [claude] CAL-OQ5-05
@BUG_1869
def test_cal_oq5_05__the_projects_creator_sees_a_private_project(db, st, mk):
    """CAL-OQ5-05 — the project's creator sees a private project.
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    pv = mk.proj("Secret", start_date=SECRET_AT, created_by=ux.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == sorted([pv.id, pw.id])


# [claude] CAL-OQ5-06
@BUG_1869
def test_cal_oq5_06__a_project_member_sees_a_private_project(db, st, mk):
    """CAL-OQ5-06 — a project member sees a private project.
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    pv = mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    mk.project_member(pv, ux)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == sorted([pv.id, pw.id])


# [claude] CAL-OQ5-07
@BUG_1869
def test_cal_oq5_07__an_inactive_ground_team_manager_does_not_see_a_private_project(db, st, mk):
    """CAL-OQ5-07 — an inactive ground-team-manager does not see a private project (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team-manager", status="inactive")
    mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == [pw.id]


# [claude] CAL-OQ5-08
@BUG_1869
def test_cal_oq5_08__a_private_project_with_no_creator_is_refused_to_a_plain_member(db, st, mk):
    """CAL-OQ5-08 — a private project with no creator is refused to a plain member (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    mk.proj("Secret", start_date=SECRET_AT, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == [pw.id]


# [claude] CAL-OQ5-09
@BUG_1869
def test_cal_oq5_09__a_member_of_another_project_only_does_not_see_this_private_project(db, st, mk):
    """CAL-OQ5-09 — a member of another project only does not see this private project (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    po = mk.proj("Other", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    mk.project_member(po, ux)
    mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == sorted([po.id, pw.id])


# [claude] CAL-OQ5-10
@BUG_1869
def test_cal_oq5_10__the_owner_of_another_workspace_only_does_not_see_this_private_project(db, st, mk):
    """CAL-OQ5-10 — the owner of another workspace only does not see this private project (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    mk.member(ux, "ground-team")
    st.w2.owner_user_id = ux.id
    db.flush()
    mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == [pw.id]


# [claude] CAL-OQ5-11
@BUG_1869
def test_cal_oq5_11__a_caller_privileged_only_in_other_workspaces_does_not_see_this_private_project(db, st, mk):
    """CAL-OQ5-11 — a caller privileged only in other workspaces does not see this private project (refused caller).
    Rules: `_collect_projects` R6 [BUG-1869]; `get_events` R7"""
    ux = make_profile(db)
    _add(db, WorkspaceMember(workspace_id=st.w2.id, user_id=ux.id, role="owner", status="active"))
    _add(db, WorkspaceMember(workspace_id=st.w0.id, user_id=ux.id, role="ground-team-manager", status="active"))
    mk.member(ux, "ground-team")
    mk.proj("Secret", start_date=SECRET_AT, created_by=st.u1.id, **mk.private)
    pw = mk.proj("Open", start_date=SECRET_AT)
    result = svc.get_events(db, workspace_id=st.w1.id, start=START, end=END, types=[CC.projects], user_id=ux.id)
    # Then 1
    assert recs(result) == [pw.id]
