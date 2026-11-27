"""Unit tests for app/services/machine_work_service.py.

Implements tests/unit/services/machine_work_service.cases.md (Revision 3a), one
test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint and the fixture's outer rollback discards
everything. Nothing is patched (Conventions: no externals); the only
`patch.object` calls are the commit/rollback spies of the TC6 cards.

Row names of the cards are the lower-case names here (O1 -> o1, `W1.id` ->
`w1.id`); `# Then N` marks the checks of the card's Then line N. The standing
rows (W0, W1, W2, U1, F0, F1, F2, F9, WT0, WT1, WT9) are built in every test by
the autouse fixture `standing`; Given rows are built by the `g` fixture.
"""
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import event, func, inspect, select

from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.schemas.machine_work import MachineUpcomingWorkRow
from app.services.machine_work_service import MachineWorkService, machine_work_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc"
svc = machine_work_service

# Convention "MISSING"
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001

# Convention "SFX": the per-process suffix of order numbers
SFX = str(os.getpid())

# Convention "Window dates"
BEFORE = date(2030, 3, 9)
START = date(2030, 3, 10)
MID = date(2030, 3, 15)
END = date(2030, 3, 20)
AFTER = date(2030, 3, 21)

# Convention "Helper date"
TODAY = date(2030, 6, 15)


def TD(n):
    return TODAY + timedelta(days=n)


BUG_1571 = "BUG-1571: Upcoming machine work shows another workspace's machine"
BUG_1572 = "BUG-1572: Upcoming machine work lists machines of a deleted factory"


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows (every test, in this order)
# --------------------------------------------------------------------------- #

@pytest.fixture
def w0(db):
    return make_workspace(db)


@pytest.fixture
def w1(db, w0):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def f0(db, w0, u1):
    return _add(db, Factory(workspace_id=w0.id, name="Zero Works", abbreviation="ZW"))


@pytest.fixture
def f1(db, w1, f0):
    return _add(db, Factory(workspace_id=w1.id, name="Main Plant", abbreviation="MP"))


@pytest.fixture
def f2(db, w1, f1):
    return _add(db, Factory(workspace_id=w1.id, name="North Yard", abbreviation="NY"))


@pytest.fixture
def f9(db, w2, f2):
    return _add(db, Factory(workspace_id=w2.id, name="Far Depot", abbreviation="FR"))


@pytest.fixture
def wt0(db, w0, f9):
    return _add(db, WorkOrderType(workspace_id=w0.id, name="Zero Repair"))


@pytest.fixture
def wt1(db, w1, wt0):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))


@pytest.fixture
def wt9(db, w2, wt1):
    return _add(db, WorkOrderType(workspace_id=w2.id, name="Far Repair"))


@pytest.fixture(autouse=True)
def standing(wt9):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

class Given:
    """Builders for the Given rows; each inserts one row and flushes."""

    def __init__(self, db, w0, w1, w2, u1, f0, f1, f2, f9, wt0, wt1, wt9):
        self.db = db
        self.w0, self.w1, self.w2, self.u1 = w0, w1, w2, u1
        self.f0, self.f1, self.f2, self.f9 = f0, f1, f2, f9
        self.wt0, self.wt1, self.wt9 = wt0, wt1, wt9

    # Convention "gone" for a machine
    def gone_machine(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.u1.id}

    # Convention "gone" for a factory, section or type
    def gone(self):
        return {"is_deleted": True, "deleted_at": T0, "deleted_by": self.u1.id}

    # Convention "machine"
    def machine(self, name, **but):
        fields = {"workspace_id": self.w1.id, "factory_id": self.f1.id, "name": name}
        fields.update(but)
        return _add(self.db, Machine(**fields))

    # Recipes M0, M1, M2, M3, M9, MX
    def m0(self):
        return self.machine("Zero Press", workspace_id=self.w0.id, factory_id=self.f0.id)

    def m1(self):
        return self.machine("Lathe")

    def m2(self):
        return self.machine("Press")

    def m3(self):
        return self.machine("Drill", factory_id=self.f2.id)

    def m9(self):
        return self.machine("Grinder", workspace_id=self.w2.id, factory_id=self.f9.id)

    def mx(self):
        return self.machine("Old Saw", **self.gone_machine())

    # Convention "order L of M"
    def order(self, label, m, **but):
        fields = {
            "workspace_id": self.w1.id,
            "work_order_number": "WO-" + label + "-" + SFX,
            "work_order_type_id": self.wt1.id,
            "title": "Service",
            "factory_id": self.f1.id,
            "machine_id": m.id,
            "planned_date": MID,
            "status": "DRAFT",
        }
        fields.update(but)
        return _add(self.db, WorkOrder(**fields))

    # Convention "zero order L of M"
    def zero_order(self, label, m, **but):
        fields = {"workspace_id": self.w0.id, "work_order_type_id": self.wt0.id, "factory_id": self.f0.id}
        fields.update(but)
        return self.order(label, m, **fields)

    # Convention "far order L of M"
    def far_order(self, label, m, **but):
        fields = {"workspace_id": self.w2.id, "work_order_type_id": self.wt9.id, "factory_id": self.f9.id}
        fields.update(but)
        return self.order(label, m, **fields)

    def factory(self, name, abbreviation, **but):
        fields = {"workspace_id": self.w1.id, "name": name, "abbreviation": abbreviation}
        fields.update(but)
        return _add(self.db, Factory(**fields))

    def section(self, factory, name, **but):
        fields = {"workspace_id": self.w1.id, "factory_id": factory.id, "name": name}
        fields.update(but)
        return _add(self.db, FactorySection(**fields))

    def wtype(self, name, **but):
        fields = {"workspace_id": self.w1.id, "name": name}
        fields.update(but)
        return _add(self.db, WorkOrderType(**fields))

    # Convention "link of M to S"
    def link(self, m, s):
        row = _add(self.db, MachineSectionAssignment(
            workspace_id=self.w1.id, machine_id=m.id, factory_section_id=s.id,
        ))
        self.db.expire_all()
        return row


@pytest.fixture
def g(db, w0, w1, w2, u1, f0, f1, f2, f9, wt0, wt1, wt9):
    return Given(db, w0, w1, w2, u1, f0, f1, f2, f9, wt0, wt1, wt9)


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def pairs(x):
    return {(o.id, m.id) for (o, m) in x}


def oids(x):
    return {o.id for (o, m) in x}


def count_machines_named(db, name):
    return db.scalar(select(func.count()).select_from(Machine).where(Machine.name == name))


def reread_machine(db, machine_id):
    db.expire_all()
    return db.scalar(select(Machine).where(Machine.id == machine_id))


# Convention "sql_log"
@contextmanager
def sql_log(db):
    log = []
    conn = db.connection()

    def _record(conn_, cursor, statement, parameters, context, executemany):
        log.append(statement)

    event.listen(conn, "before_cursor_execute", _record)
    try:
        yield log
    finally:
        event.remove(conn, "before_cursor_execute", _record)


# Convention "spies"
@contextmanager
def spies(db):
    from unittest.mock import patch
    with patch.object(db, "commit", wraps=db.commit) as cm, \
            patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# =========================================================================== #
# MachineWorkService.collect_raw_items
# =========================================================================== #

def test_mws_cr_01__open_dated_order_returned_with_machine(db, g, w1):
    """MWS-CR-01 — an open dated order on a live machine is returned with its machine.
    Rules: collect_raw_items R1, Returns (G4)."""
    m1 = g.m1()
    o1 = g.order("O1", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 1
    # Then 3
    wo, machine = result[0]
    assert wo.id == o1.id
    assert machine.id == m1.id
    # Then 4
    assert result[0][0] is wo
    assert result[0][1] is machine
    # Then 5
    assert len(result[0]) == 2
    # Then 6
    assert result[0] == (wo, machine)
    # Then 7
    assert isinstance(wo, WorkOrder)
    assert isinstance(machine, Machine)
    # Then 8
    assert pairs(result) == {(o1.id, m1.id)}


def test_mws_cr_02__window_includes_start_and_end(db, g, w1):
    """MWS-CR-02 — the window includes start and end, not the days outside.
    Rules: collect_raw_items R1."""
    m1 = g.m1()
    g.order("OA", m1, planned_date=AFTER)
    oe = g.order("OE", m1, planned_date=END)
    os_ = g.order("OS", m1, planned_date=START)
    g.order("OB", m1, planned_date=BEFORE)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert oids(result) == {oe.id, os_.id}


def test_mws_cr_03__end_before_start_gives_empty(db, g, w1):
    """MWS-CR-03 — end before start gives [].
    Rules: collect_raw_items R1."""
    m1 = g.m1()
    g.order("OS", m1, planned_date=START)
    g.order("OM", m1, planned_date=MID)
    g.order("OE", m1, planned_date=END)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=END, end=START)
    # Then 1
    assert result == []


def test_mws_cr_04__start_equal_end_keeps_that_day(db, g, w1):
    """MWS-CR-04 — start equal to end keeps that one day.
    Rules: collect_raw_items R1."""
    m1 = g.m1()
    om = g.order("OM", m1, planned_date=MID)
    g.order("ON", m1, planned_date=date(2030, 3, 16))
    g.order("OP", m1, planned_date=date(2030, 3, 14))
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=MID, end=MID)
    # Then 1
    assert oids(result) == {om.id}


def test_mws_cr_05__default_statuses_draft_and_in_progress(db, g, w1):
    """MWS-CR-05 — default statuses are DRAFT and IN_PROGRESS only.
    Rules: collect_raw_items R1."""
    m1 = g.m1()
    od = g.order("OD", m1)
    op = g.order("OP", m1, status="IN_PROGRESS")
    g.order("OC", m1, status="COMPLETED")
    g.order("OV", m1, status="VOIDED")
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert oids(result) == {od.id, op.id}


def test_mws_cr_06__default_statuses_match_exactly(db, g, w1):
    """MWS-CR-06 — default statuses match the stored text exactly.
    Rules: collect_raw_items R2."""
    m1 = g.m1()
    ok = g.order("OK", m1)
    g.order("O1", m1, status="draft")
    g.order("O2", m1, status=" DRAFT")
    g.order("O3", m1, status="DRAF")
    g.order("O4", m1, status="INXPROGRESS")
    g.order("O5", m1, status="IN_PROGRESS_X")
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert oids(result) == {ok.id}


def test_mws_cr_07__given_statuses_match_exactly(db, g, w1):
    """MWS-CR-07 — given statuses match exactly on the argument side.
    Rules: collect_raw_items R2."""
    m1 = g.m1()
    g.order("OP", m1, status="IN_PROGRESS")
    commit_point(db)
    result = svc.collect_raw_items(
        db, workspace_id=w1.id, start=START, end=END,
        statuses=["in_progress", " IN_PROGRESS", "IN_PROG", "IN%", "IN_PROGRES_"],
    )
    # Then 1
    assert result == []


def test_mws_cr_08__statuses_in_progress_only(db, g, w1):
    """MWS-CR-08 — statuses=["IN_PROGRESS"] matches IN_PROGRESS only.
    Rules: collect_raw_items R2."""
    m1 = g.m1()
    g.order("OD", m1)
    op = g.order("OP", m1, status="IN_PROGRESS")
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, statuses=["IN_PROGRESS"])
    # Then 1
    assert oids(result) == {op.id}


def test_mws_cr_09__empty_statuses_gives_empty(db, g, w1):
    """MWS-CR-09 — statuses=[] gives [].
    Rules: collect_raw_items R2."""
    m1 = g.m1()
    g.order("OD", m1)
    g.order("OP", m1, status="IN_PROGRESS")
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, statuses=[])
    # Then 1
    assert result == []


def test_mws_cr_10__unknown_status_matches_nothing(db, g, w1):
    """MWS-CR-10 — an unknown status raises nothing and matches nothing.
    Rules: collect_raw_items R2."""
    m1 = g.m1()
    g.order("OD", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, statuses=["NOPE"])
    # Then 1
    assert result == []


def test_mws_cr_11__given_statuses_replace_defaults(db, g, w1):
    """MWS-CR-11 — given statuses replace the defaults.
    Rules: collect_raw_items R1, R2."""
    m1 = g.m1()
    g.order("OD", m1)
    oc = g.order("OC", m1, status="COMPLETED")
    ov = g.order("OV", m1, status="VOIDED")
    commit_point(db)
    result = svc.collect_raw_items(
        db, workspace_id=w1.id, start=START, end=END, statuses=["COMPLETED", "VOIDED"],
    )
    # Then 1
    assert oids(result) == {oc.id, ov.id}


def test_mws_cr_12__deleted_undated_machineless_orders_left_out(db, g, w1, u1):
    """MWS-CR-12 — soft-deleted, undated and machine-less orders are never returned.
    Rules: collect_raw_items R1."""
    m1 = g.m1()
    g.order("OX", m1, is_deleted=True, deleted_at=T0, deleted_by=u1.id)
    g.order("ON", m1, planned_date=None)
    g.order("OM", m1, machine_id=None)
    ok = g.order("OK", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, statuses=["DRAFT"])
    # Then 1
    assert oids(result) == {ok.id}


def test_mws_cr_13__deleted_machine_left_out_inactive_kept(db, g, w1):
    """MWS-CR-13 — a soft-deleted machine's orders are left out; an inactive machine's are kept.
    Rules: collect_raw_items R3."""
    mx = g.mx()
    mi = g.machine("Idle Mill", is_active=False)
    g.order("OX", mx)
    oi = g.order("OI", mi)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(oi.id, mi.id)}


def test_mws_cr_14__orders_of_w0_and_w2_not_returned(db, g, w1):
    """MWS-CR-14 — orders of W0 and W2 are never returned to W1.
    Rules: collect_raw_items R1."""
    m0 = g.m0()
    m1 = g.m1()
    m9 = g.m9()
    g.zero_order("Z0", m0)
    o1 = g.order("O1", m1)
    g.far_order("Z9", m9)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(o1.id, m1.id)}


@pytest.mark.xfail(strict=True, reason=BUG_1571)
def test_mws_cr_15__w1_order_on_w2_machine_left_out(db, g, w1):
    """MWS-CR-15 — BUG-1571: a W1 order naming W2's machine is left out.
    Rules: collect_raw_items R4 [BUG-1571]."""
    m1 = g.m1()
    m9 = g.m9()
    o1 = g.order("O1", m1)
    g.order("OS", m9)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(o1.id, m1.id)}
    # Then 2
    assert m9.id not in {m.id for (o, m) in result}


@pytest.mark.xfail(strict=True, reason=BUG_1571)
def test_mws_cr_16__w1_order_on_w0_machine_left_out(db, g, w1):
    """MWS-CR-16 — BUG-1571: a W1 order naming W0's machine (lower id) is left out.
    Rules: collect_raw_items R4 [BUG-1571]."""
    m0 = g.m0()
    m1 = g.m1()
    g.order("OS", m0)
    o1 = g.order("O1", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(o1.id, m1.id)}
    # Then 2
    assert m0.id not in {m.id for (o, m) in result}


def test_mws_cr_17__machine_own_workspace_does_not_see_other_order(db, g, w2):
    """MWS-CR-17 — seen from the machine's own workspace, the other workspace's order is not returned.
    Rules: collect_raw_items R4."""
    m9 = g.m9()
    g.order("OS", m9)
    z9 = g.far_order("Z9", m9)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w2.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(z9.id, m9.id)}


def test_mws_cr_18__machine_of_deleted_factory_returned(db, g, w1):
    """MWS-CR-18 — a live machine of a soft-deleted factory is returned with its orders.
    Rules: collect_raw_items R5 (D2)."""
    fd = g.factory("Closed Mill", "CM", **g.gone())
    mf = g.machine("Kiln", factory_id=fd.id)
    of = g.order("OF", mf, factory_id=fd.id)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(of.id, mf.id)}


def test_mws_cr_19__factory_id_compared_with_order_factory(db, g, w1):
    """MWS-CR-19 — factory_id is compared with the order's factory, lower and higher ids left out.
    Rules: collect_raw_items R6."""
    fa = g.factory("Alpha Works", "AW")
    fb = g.factory("Beta Works", "BW")
    fc = g.factory("Gamma Works", "GW")
    ma = g.machine("Ax", factory_id=fa.id)
    mb = g.machine("Bx", factory_id=fb.id)
    mc = g.machine("Cx", factory_id=fc.id)
    g.order("OA", ma, factory_id=fa.id)
    ob = g.order("OB", mc, factory_id=fb.id)
    g.order("OC", mb, factory_id=fc.id)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, factory_id=fb.id)
    # Then 1
    assert pairs(result) == {(ob.id, mc.id)}


def test_mws_cr_20__factory_id_none_filters_nothing(db, g, w1, f2):
    """MWS-CR-20 — factory_id=None filters nothing.
    Rules: collect_raw_items R6."""
    m1 = g.m1()
    m3 = g.m3()
    o1 = g.order("O1", m1)
    o3 = g.order("O3", m3, factory_id=f2.id)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, factory_id=None)
    # Then 1
    assert oids(result) == {o1.id, o3.id}


def test_mws_cr_21__machine_ids_keeps_only_those(db, g, w1):
    """MWS-CR-21 — machine_ids keeps only those machines, lower and higher ids left out.
    Rules: collect_raw_items R6."""
    ma = g.machine("Ax")
    mb = g.machine("Bx")
    mc = g.machine("Cx")
    g.order("OA", ma)
    ob = g.order("OB", mb)
    g.order("OC", mc)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, machine_ids=[mb.id])
    # Then 1
    assert pairs(result) == {(ob.id, mb.id)}


def test_mws_cr_22__unknown_machine_id_matches_nothing(db, g, w1):
    """MWS-CR-22 — an unknown machine id matches nothing and raises nothing.
    Rules: collect_raw_items R6."""
    m1 = g.m1()
    g.order("O1", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, machine_ids=[MISSING])
    # Then 1
    assert result == []


def test_mws_cr_23__empty_machine_ids_gives_empty(db, g, w1):
    """MWS-CR-23 — machine_ids=[] gives [].
    Rules: collect_raw_items R6, R2."""
    m1 = g.m1()
    g.order("O1", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END, machine_ids=[])
    # Then 1
    assert result == []


def test_mws_cr_24__query_takes_no_row_lock(db, g, w1):
    """MWS-CR-24 — the query takes no row lock.
    Rules: collect_raw_items R7."""
    m1 = g.m1()
    o1 = g.order("O1", m1)
    ws_id = w1.id  # read before the log: the commit point expires W1
    commit_point(db)
    with sql_log(db) as log:
        result = svc.collect_raw_items(db, workspace_id=ws_id, start=START, end=END)
    # Then 1
    assert oids(result) == {o1.id}
    # Then 2
    assert len(log) >= 1
    # Then 3
    assert all("FOR UPDATE" not in s.upper() for s in log)


def test_mws_cr_25__neither_commits_nor_rolls_back(db, g, w1):
    """MWS-CR-25 — collect_raw_items neither commits nor rolls back.
    Rules: collect_raw_items R7; TC6."""
    a = g.m1()
    b = g.m2()
    o1 = g.order("O1", a)
    commit_point(db)
    p = g.machine("Pending")
    b.name = "Edited"
    with spies(db) as (cm, rb):
        result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(o1.id, a.id)}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert p in db
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    db.rollback()
    # Then 7
    assert count_machines_named(db, "Pending") == 0
    # Then 8
    assert reread_machine(db, b.id).name == "Press"


def test_mws_cr_26__is_deleted_alone_leaves_machine_out(db, g, w1):
    """MWS-CR-26 — a machine with only is_deleted set is left out; deleted_at and is_active are not needed.
    Rules: collect_raw_items R3 (Notes G1)."""
    md = g.machine("Half Gone", is_deleted=True, is_active=True, deleted_at=None, deleted_by=None)
    m1 = g.m1()
    g.order("OD", md)
    o1 = g.order("O1", m1)
    commit_point(db)
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(o1.id, m1.id)}
    # Then 2
    assert md.id not in {m.id for (o, m) in result}


def test_mws_cr_27__section_assignment_and_section_loaded(db, g, w1, f2):
    """MWS-CR-27 — the machine's section assignment and its section are loaded by the query.
    Rules: collect_raw_items Returns (Notes G2)."""
    s1 = g.section(f2, "Cutting")
    m3 = g.m3()
    m1 = g.m1()
    g.link(m3, s1)
    o3 = g.order("O3", m3)
    o1 = g.order("O1", m1)
    ids = {"s1": s1.id, "m3": m3.id, "m1": m1.id, "o3": o3.id, "o1": o1.id}
    commit_point(db)
    db.expire_all()
    result = svc.collect_raw_items(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert pairs(result) == {(ids["o3"], ids["m3"]), (ids["o1"], ids["m1"])}
    # Then 2
    ma = next(m for (o, m) in result if o.id == ids["o3"])
    mb = next(m for (o, m) in result if o.id == ids["o1"])
    assert "section_assignment" not in inspect(ma).unloaded
    # Then 3
    assert "section_assignment" not in inspect(mb).unloaded
    # Then 4
    assert "factory_section" not in inspect(ma.section_assignment).unloaded
    # Then 5
    assert ma.section_assignment.factory_section.id == ids["s1"]
    assert ma.section_assignment.factory_section.name == "Cutting"
    # Then 6
    assert mb.section_assignment is None


# =========================================================================== #
# MachineWorkService.upcoming_work
# =========================================================================== #

def test_mws_uw_01__no_order_gives_empty(db, g, w1):
    """MWS-UW-01 — no order gives [].
    Rules: upcoming_work R1."""
    g.m1()
    g.m2()
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert result == []


def test_mws_uw_02__window_and_default_statuses_reach_query(db, g, w1):
    """MWS-UW-02 — the window and the default open statuses reach the query.
    Rules: upcoming_work R1."""
    m1 = g.m1()
    g.order("OB", m1, planned_date=BEFORE)
    os_ = g.order("OS", m1, planned_date=START)
    oe = g.order("OE", m1, planned_date=END, status="IN_PROGRESS")
    g.order("OA", m1, planned_date=AFTER)
    g.order("OC", m1, status="COMPLETED")
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert isinstance(result[0], MachineUpcomingWorkRow)
    # Then 3
    assert [i.source_id for i in result[0].items] == [os_.id, oe.id]


def test_mws_uw_03__factory_filter_on_order_row_shows_machine_factory(db, g, w1, f1, f2):
    """MWS-UW-03 — factory_id filters on the order's factory; the row shows the machine's factory.
    Rules: upcoming_work R1, R3."""
    m1 = g.m1()
    m3 = g.m3()
    o1 = g.order("O1", m1, factory_id=f2.id)
    g.order("O3", m3, factory_id=f1.id)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END, factory_id=f2.id)
    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert result[0].factory_id == f1.id
    # Then 3
    assert [i.source_id for i in result[0].items] == [o1.id]


def test_mws_uw_04__machine_ids_reaches_query(db, g, w1):
    """MWS-UW-04 — machine_ids reaches the query.
    Rules: upcoming_work R1."""
    ma = g.machine("Ax")
    mb = g.machine("Bx")
    mc = g.machine("Cx")
    g.order("OA", ma)
    g.order("OB", mb)
    g.order("OC", mc)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END, machine_ids=[mb.id])
    # Then 1
    assert [r.machine_id for r in result] == [mb.id]


def test_mws_uw_05__one_row_per_machine_with_counts(db, g, w1):
    """MWS-UW-05 — one row per machine; count and sources equal its number of orders.
    Rules: upcoming_work R2."""
    m1 = g.m1()
    m2 = g.m2()
    g.order("O1", m1, planned_date=START)
    g.order("O2", m2, planned_date=START)
    g.order("O3", m1, planned_date=START)
    g.order("O4", m1, planned_date=START)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [m1.id, m2.id]
    # Then 2
    assert result[0].count == 3
    assert result[0].sources.work_orders == 3
    assert len(result[0].items) == 3
    # Then 3
    assert result[1].count == 1
    assert result[1].sources.work_orders == 1
    assert len(result[1].items) == 1


def test_mws_uw_06__row_shows_name_factory_section(db, g, w1, f1, f2):
    """MWS-UW-06 — the row shows the machine's name, factory and section; no section gives None.
    Rules: upcoming_work R3."""
    s1 = g.section(f2, "Cutting")
    m3 = g.m3()
    m1 = g.m1()
    g.link(m3, s1)
    g.order("O3", m3, planned_date=START)
    g.order("O1", m1, planned_date=END)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [m3.id, m1.id]
    # Then 2
    assert result[0].name == "Drill"
    assert result[0].factory_id == f2.id
    # Then 3
    assert result[0].factory_section_id == s1.id
    assert result[0].section_name == "Cutting"
    # Then 4
    assert result[1].name == "Lathe"
    assert result[1].factory_id == f1.id
    # Then 5
    assert result[1].factory_section_id is None
    assert result[1].section_name is None


def test_mws_uw_07__deleted_section_still_shown(db, g, w1, f1):
    """MWS-UW-07 — a soft-deleted section is still shown.
    Rules: upcoming_work R3 (D3)."""
    sx = g.section(f1, "Line B", **g.gone())
    m1 = g.m1()
    g.link(m1, sx)
    g.order("O1", m1)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].factory_section_id == sx.id
    assert result[0].section_name == "Line B"


def test_mws_uw_08__each_order_one_item_empty_title_shows_number(db, g, w1):
    """MWS-UW-08 — each order is one item with its own values; an empty title shows the number.
    Rules: upcoming_work R4."""
    wt2 = g.wtype("Servicing")
    m1 = g.m1()
    o1 = g.order("O1", m1, planned_date=START, title="Belt check")
    o2 = g.order("O2", m1, planned_date=MID, title="", status="IN_PROGRESS", work_order_type_id=wt2.id)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.kind for i in result[0].items] == ["work_order", "work_order"]
    # Then 3
    assert [i.source_id for i in result[0].items] == [o1.id, o2.id]
    # Then 4
    assert [i.date for i in result[0].items] == [START, MID]
    # Then 5
    assert [i.title for i in result[0].items] == ["Belt check", "WO-O2-" + SFX]
    # Then 6
    assert [i.status for i in result[0].items] == ["DRAFT", "IN_PROGRESS"]
    # Then 7
    assert [i.work_order_type_name for i in result[0].items] == ["Repair", "Servicing"]


def test_mws_uw_09__deleted_type_name_still_shown(db, g, w1):
    """MWS-UW-09 — a soft-deleted work order type's name is still shown.
    Rules: upcoming_work R4 (D4)."""
    wtx = g.wtype("Servicing", **g.gone())
    m1 = g.m1()
    g.order("O1", m1, work_order_type_id=wtx.id)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.work_order_type_name for i in result[0].items] == ["Servicing"]


def test_mws_uw_10__items_sort_by_date_then_id(db, g, w1):
    """MWS-UW-10 — items sort by date then order id; earliest_date is the smallest date.
    Rules: upcoming_work R5."""
    m1 = g.m1()
    oa = g.order("OA", m1, planned_date=END)
    ob = g.order("OB", m1, planned_date=START)
    oc = g.order("OC", m1, planned_date=MID)
    od = g.order("OD", m1, planned_date=START)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert [i.source_id for i in result[0].items] == [ob.id, od.id, oc.id, oa.id]
    # Then 3
    assert result[0].earliest_date == START


def test_mws_uw_11__rows_sort_by_date_name_ci_then_id(db, g, w1, f2):
    """MWS-UW-11 — rows sort by earliest date, then name ignoring case, then machine id.
    Rules: upcoming_work R5."""
    x1 = g.machine("gamma")
    x2 = g.machine("Beta")
    x3 = g.machine("Gamma", factory_id=f2.id)
    x4 = g.machine("alpha")
    x5 = g.machine("Zed")
    g.order("A1", x1, planned_date=MID)
    g.order("A2", x2, planned_date=date(2030, 3, 12))
    g.order("A3", x3, planned_date=MID)
    g.order("A4", x4, planned_date=date(2030, 3, 12))
    g.order("A5", x5, planned_date=END)
    g.order("A6", x5, planned_date=START)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.name for r in result] == ["Zed", "alpha", "Beta", "gamma", "Gamma"]
    # Then 2
    assert [r.machine_id for r in result] == [x5.id, x4.id, x2.id, x1.id, x3.id]
    # Then 3
    assert [r.earliest_date for r in result] == [START, date(2030, 3, 12), date(2030, 3, 12), MID, MID]


def test_mws_uw_12__every_row_returned_101_machines(db, g, w1):
    """MWS-UW-12 — every row is returned, 101 machines give 101 rows.
    Rules: upcoming_work R5."""
    machines = [g.machine("P" + str(n).zfill(5)) for n in range(101)]
    for n, m in enumerate(machines):
        g.order("N" + str(n), m)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].name == "P00000"
    assert result[100].name == "P00100"


@pytest.mark.xfail(strict=True, reason=BUG_1572)
def test_mws_uw_13__machine_of_deleted_factory_left_out(db, g, w1):
    """MWS-UW-13 — BUG-1572: a live machine of a soft-deleted factory is left out with its orders.
    Rules: upcoming_work R6 [BUG-1572]."""
    fd = g.factory("Closed Mill", "CM", **g.gone())
    mf = g.machine("Kiln", factory_id=fd.id)
    m1 = g.m1()
    g.order("OF", mf, factory_id=fd.id)
    g.order("O1", m1)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert "Kiln" not in [r.name for r in result]


@pytest.mark.xfail(strict=True, reason=BUG_1571)
def test_mws_uw_14__w1_order_on_w2_machine_left_out(db, g, w1, f9):
    """MWS-UW-14 — BUG-1571: a W1 order on W2's machine is left out; nothing of W2 shown.
    Rules: upcoming_work R1 via collect_raw_items R4 [BUG-1571]."""
    m1 = g.m1()
    m9 = g.m9()
    g.order("O1", m1, planned_date=END)
    g.order("OS", m9, planned_date=START)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [m1.id]
    # Then 2
    assert "Grinder" not in [r.name for r in result]
    # Then 3
    assert f9.id not in [r.factory_id for r in result]


def test_mws_uw_15__inactive_live_factory_hides_nothing(db, g, w1):
    """MWS-UW-15 — an inactive but live factory hides nothing.
    Rules: upcoming_work R6."""
    fi = g.factory("Quiet Plant", "QP", is_active=False)
    mq = g.machine("Quill", factory_id=fi.id)
    g.order("OQ", mq, factory_id=fi.id)
    commit_point(db)
    result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [mq.id]
    # Then 2
    assert result[0].factory_id == fi.id


def test_mws_uw_16__neither_commits_nor_rolls_back(db, g, w1):
    """MWS-UW-16 — upcoming_work neither commits nor rolls back.
    Rules: upcoming_work R7; TC6."""
    a = g.m1()
    b = g.m2()
    g.order("O1", a)
    commit_point(db)
    p = g.machine("Pending")
    b.name = "Edited"
    with spies(db) as (cm, rb):
        result = svc.upcoming_work(db, workspace_id=w1.id, start=START, end=END)
    # Then 1
    assert [r.machine_id for r in result] == [a.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert p in db
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    db.rollback()
    # Then 7
    assert count_machines_named(db, "Pending") == 0
    # Then 8
    assert reread_machine(db, b.id).name == "Press"


# =========================================================================== #
# MachineWorkService.dates_by_machine
# =========================================================================== #

def test_mws_dm_01__empty_ids_no_database_read(db, g, w1):
    """MWS-DM-01 — machine_ids=[] gives {} without reading the database.
    Rules: dates_by_machine R1."""
    m1 = g.m1()
    g.order("O1", m1)
    ws_id = w1.id  # read before the log: the commit point expires W1
    commit_point(db)
    with sql_log(db) as log:
        result = svc.dates_by_machine(db, workspace_id=ws_id, machine_ids=[], start=START, end=END)
    # Then 1
    assert result == {}
    # Then 2
    assert log == []


def test_mws_dm_02__empty_generator_no_database_read(db, g, w1):
    """MWS-DM-02 — an empty generator gives {} without reading the database.
    Rules: dates_by_machine R1."""
    m1 = g.m1()
    g.order("O1", m1)
    ws_id = w1.id  # read before the log: the commit point expires W1
    commit_point(db)
    with sql_log(db) as log:
        result = svc.dates_by_machine(
            db, workspace_id=ws_id, machine_ids=(i for i in []), start=START, end=END,
        )
    # Then 1
    assert result == {}
    # Then 2
    assert log == []


def test_mws_dm_03__one_date_per_order_sorted(db, g, w1, f2):
    """MWS-DM-03 — one date per order, duplicates kept, each list ascending whatever order the rows come back in.
    Rules: dates_by_machine R2."""
    m1 = g.m1()
    m2 = g.m2()
    m3 = g.m3()
    g.order("O1", m1, planned_date=END)
    g.order("O2", m1, planned_date=MID)
    g.order("O3", m1, planned_date=START)
    g.order("O4", m1, planned_date=MID)
    g.order("O5", m2, planned_date=START, status="IN_PROGRESS")
    g.order("O6", m2, planned_date=END)
    g.order("O7", m3, planned_date=MID, factory_id=f2.id)
    g.order("O8", m3, planned_date=START, factory_id=f2.id)
    g.order("O9", m3, planned_date=END, factory_id=f2.id)
    commit_point(db)
    result = svc.dates_by_machine(
        db, workspace_id=w1.id, machine_ids=[m1.id, m2.id, m3.id], start=START, end=END
    )
    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert result == {m1.id: [START, MID, MID, END], m2.id: [START, END], m3.id: [START, MID, END]}
    # Then 3
    assert all(v == sorted(v) for v in result.values())


def test_mws_dm_04__generator_of_ids_works(db, g, w1):
    """MWS-DM-04 — a generator of ids is read once and works.
    Rules: dates_by_machine Inputs, R2."""
    m1 = g.m1()
    m2 = g.m2()
    g.order("O1", m1, planned_date=START)
    g.order("O2", m2, planned_date=END)
    commit_point(db)
    result = svc.dates_by_machine(
        db, workspace_id=w1.id, machine_ids=(i for i in [m1.id, m2.id]), start=START, end=END,
    )
    # Then 1
    assert result == {m1.id: [START], m2.id: [END]}


def test_mws_dm_05__window_includes_start_and_end(db, g, w1):
    """MWS-DM-05 — the window includes start and end, not the days outside.
    Rules: dates_by_machine R2."""
    m1 = g.m1()
    g.order("OA", m1, planned_date=AFTER)
    g.order("OE", m1, planned_date=END)
    g.order("OS", m1, planned_date=START)
    g.order("OB", m1, planned_date=BEFORE)
    commit_point(db)
    result = svc.dates_by_machine(db, workspace_id=w1.id, machine_ids=[m1.id], start=START, end=END)
    # Then 1
    assert result == {m1.id: [START, END]}


def test_mws_dm_06__statuses_in_progress_only(db, g, w1):
    """MWS-DM-06 — statuses=("IN_PROGRESS",) keeps only in-progress dates; default leaves out closed orders.
    Rules: dates_by_machine R2, R3."""
    m1 = g.m1()
    m2 = g.m2()
    g.order("O1", m1, planned_date=START, status="IN_PROGRESS")
    g.order("O2", m1, planned_date=MID)
    g.order("O3", m2, planned_date=MID)
    g.order("O4", m2, planned_date=END, status="COMPLETED")
    commit_point(db)
    result = svc.dates_by_machine(
        db, workspace_id=w1.id, machine_ids=[m1.id, m2.id], start=START, end=END,
        statuses=("IN_PROGRESS",),
    )
    # Then 1
    assert result == {m1.id: [START]}


def test_mws_dm_07__unknown_deleted_unmatched_unasked_absent(db, g, w1):
    """MWS-DM-07 — unknown ids, soft-deleted machines, machines with no match and machines not asked are absent.
    Rules: dates_by_machine R3."""
    mx = g.mx()
    m1 = g.m1()
    m2 = g.m2()
    m3 = g.m3()
    g.order("OX", mx)
    g.order("O1", m1)
    g.order("O2", m2, status="COMPLETED")
    g.order("O3", m3)
    commit_point(db)
    result = svc.dates_by_machine(
        db, workspace_id=w1.id, machine_ids=[MISSING, mx.id, m1.id, m2.id], start=START, end=END,
    )
    # Then 1
    assert result == {m1.id: [MID]}


def test_mws_dm_08__machine_of_deleted_factory_keeps_dates(db, g, w1):
    """MWS-DM-08 — a machine of a soft-deleted factory keeps its dates.
    Rules: dates_by_machine R3 (D2)."""
    fd = g.factory("Closed Mill", "CM", **g.gone())
    mf = g.machine("Kiln", factory_id=fd.id)
    g.order("OF", mf, factory_id=fd.id)
    commit_point(db)
    result = svc.dates_by_machine(db, workspace_id=w1.id, machine_ids=[mf.id], start=START, end=END)
    # Then 1
    assert result == {mf.id: [MID]}


@pytest.mark.xfail(strict=True, reason=BUG_1571)
def test_mws_dm_09__other_workspace_machine_absent(db, g, w1):
    """MWS-DM-09 — BUG-1571: another workspace's machine is absent.
    Rules: dates_by_machine R3 [BUG-1571] (D1)."""
    m1 = g.m1()
    m9 = g.m9()
    g.order("O1", m1, planned_date=START)
    g.order("OS", m9, planned_date=END)
    commit_point(db)
    result = svc.dates_by_machine(db, workspace_id=w1.id, machine_ids=[m9.id, m1.id], start=START, end=END)
    # Then 1
    assert result == {m1.id: [START]}


def test_mws_dm_10__w0_and_w2_orders_never_reach_w1(db, g, w1):
    """MWS-DM-10 — orders of W0 and W2 on their own machines never reach W1; seen from W2 the W1 order is absent.
    Rules: dates_by_machine R2, R3."""
    m0 = g.m0()
    m1 = g.m1()
    m9 = g.m9()
    g.zero_order("Z0", m0)
    g.order("O1", m1, planned_date=START)
    g.far_order("Z9", m9)
    commit_point(db)
    result = svc.dates_by_machine(
        db, workspace_id=w1.id, machine_ids=[m0.id, m1.id, m9.id], start=START, end=END,
    )
    # Then 1
    assert result == {m1.id: [START]}


def test_mws_dm_11__machine_own_workspace_gets_no_date(db, g, w2):
    """MWS-DM-11 — seen from the machine's own workspace, a W1 order on it gives no date.
    Rules: dates_by_machine R3 (via collect_raw_items R4)."""
    m9 = g.m9()
    g.order("OS", m9)
    commit_point(db)
    result = svc.dates_by_machine(db, workspace_id=w2.id, machine_ids=[m9.id], start=START, end=END)
    # Then 1
    assert result == {}


def test_mws_dm_12__neither_commits_nor_rolls_back(db, g, w1):
    """MWS-DM-12 — dates_by_machine neither commits nor rolls back.
    Rules: dates_by_machine R4; TC6."""
    a = g.m1()
    b = g.m2()
    g.order("O1", a)
    commit_point(db)
    p = g.machine("Pending")
    b.name = "Edited"
    with spies(db) as (cm, rb):
        result = svc.dates_by_machine(db, workspace_id=w1.id, machine_ids=[a.id, b.id], start=START, end=END)
    # Then 1
    assert result == {a.id: [MID]}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert p in db
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    db.rollback()
    # Then 7
    assert count_machines_named(db, "Pending") == 0
    # Then 8
    assert reread_machine(db, b.id).name == "Press"


# =========================================================================== #
# MachineWorkService.earliest_upcoming_on_or_after
# =========================================================================== #

def test_mws_eu_01__earliest_on_or_after_from_unsorted():
    """MWS-EU-01 — the earliest date on or after from_date, from an unsorted list.
    Rules: earliest_upcoming_on_or_after R1."""
    result = MachineWorkService.earliest_upcoming_on_or_after([TD(5), TD(-3), TD(2), TD(9)], TODAY)
    # Then 1
    assert result == TD(2)


def test_mws_eu_02__date_equal_from_date_counts():
    """MWS-EU-02 — a date equal to from_date counts.
    Rules: earliest_upcoming_on_or_after R1."""
    result = MachineWorkService.earliest_upcoming_on_or_after([TD(4), TD(0), TD(-1)], TODAY)
    # Then 1
    assert result == TODAY


def test_mws_eu_03__only_earlier_dates_give_none():
    """MWS-EU-03 — only earlier dates give None.
    Rules: earliest_upcoming_on_or_after R2."""
    result = MachineWorkService.earliest_upcoming_on_or_after([TD(-1), TD(-10)], TODAY)
    # Then 1
    assert result is None


def test_mws_eu_04__empty_list_gives_none():
    """MWS-EU-04 — an empty list gives None.
    Rules: earliest_upcoming_on_or_after R2."""
    result = MachineWorkService.earliest_upcoming_on_or_after([], TODAY)
    # Then 1
    assert result is None


# =========================================================================== #
# MachineWorkService.has_overdue
# =========================================================================== #

def test_mws_ho_01__date_before_today_is_overdue():
    """MWS-HO-01 — a date strictly before today is overdue.
    Rules: has_overdue R1."""
    result = MachineWorkService.has_overdue([TD(3), TD(-1)], TODAY)
    # Then 1
    assert result is True


def test_mws_ho_02__today_and_later_not_overdue():
    """MWS-HO-02 — today itself and later dates are not overdue.
    Rules: has_overdue R1."""
    result = MachineWorkService.has_overdue([TD(0), TD(3)], TODAY)
    # Then 1
    assert result is False


def test_mws_ho_03__empty_list_not_overdue():
    """MWS-HO-03 — an empty list is not overdue.
    Rules: has_overdue R1."""
    result = MachineWorkService.has_overdue([], TODAY)
    # Then 1
    assert result is False


# =========================================================================== #
# MachineWorkService.has_upcoming_in_horizon
# =========================================================================== #

def test_mws_hh_01__horizon_7_today_plus_7_counts():
    """MWS-HH-01 — horizon 7: today + 7 counts.
    Rules: has_upcoming_in_horizon R1."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(7)], TODAY, 7)
    # Then 1
    assert result is True


def test_mws_hh_02__horizon_7_plus_8_and_past_do_not_count():
    """MWS-HH-02 — horizon 7: today + 8 and a past date do not count.
    Rules: has_upcoming_in_horizon R1."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(8), TD(-1)], TODAY, 7)
    # Then 1
    assert result is False


def test_mws_hh_03__horizon_7_today_counts():
    """MWS-HH-03 — horizon 7: today itself counts.
    Rules: has_upcoming_in_horizon R1."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(30), TD(0)], TODAY, 7)
    # Then 1
    assert result is True


def test_mws_hh_04__empty_list_false():
    """MWS-HH-04 — an empty list is False.
    Rules: has_upcoming_in_horizon R1."""
    result = MachineWorkService.has_upcoming_in_horizon([], TODAY, 30)
    # Then 1
    assert result is False


def test_mws_hh_05__horizon_0_today_counts():
    """MWS-HH-05 — horizon 0: today counts.
    Rules: has_upcoming_in_horizon R2."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(0)], TODAY, 0)
    # Then 1
    assert result is True


def test_mws_hh_06__horizon_0_tomorrow_yesterday_do_not_count():
    """MWS-HH-06 — horizon 0: tomorrow and yesterday do not count.
    Rules: has_upcoming_in_horizon R2."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(1), TD(-1)], TODAY, 0)
    # Then 1
    assert result is False


def test_mws_hh_07__negative_horizon_false():
    """MWS-HH-07 — a negative horizon is False, even for today.
    Rules: has_upcoming_in_horizon R2."""
    result = MachineWorkService.has_upcoming_in_horizon([TD(0), TD(-1)], TODAY, -1)
    # Then 1
    assert result is False


def test_mws_hh_08__horizon_out_of_range_raises_value_error():
    """MWS-HH-08 — a horizon past the last representable date raises ValueError, not wrapped.
    Rules: has_upcoming_in_horizon R3; TC6 (error not wrapped)."""
    # Then 1
    with pytest.raises(ValueError) as exc:
        MachineWorkService.has_upcoming_in_horizon([TODAY], TODAY, 10**7)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert "out of range" in str(exc.value)
