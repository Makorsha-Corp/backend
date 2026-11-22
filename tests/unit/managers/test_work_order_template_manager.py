"""Unit tests for app/managers/work_order_template_manager.py.

Implements tests/unit/managers/work_order_template_manager.cases.md (revision 2),
one test per card, in card order (schema-only cards that differ in one input are
parametrized, one param id per card). Real Postgres session (`db` fixture),
rolled back after each test. Nothing is mocked (Externals: none) except in the
three `Author: claude` cards: GD-43 and AR-25 patch
`work_order_manager.create_work_order_from_template` on the singleton (`wom`),
RI-07 builds a work order line row.

How to read these tests:
- Standing rows (Conventions) are built by the fixture `R` in every test:
  `R.W1`, `R.U1`, `R.WT1`, `R.F1`, `R.S1`, `R.M1`, `R.I1`, `R.A1`, ...
  A card's own Given names are lower-case locals (`t`, `s`, `z`, `l`, `o`, ...).
- `tpl(db, R, **over)` is the Conventions "template" (W1, "Oil change", WT1,
  created by U1); `tpl_w0` / `tpl_w2` the W0 / W2 templates. `WEEKLY`, `DAILY`,
  `monthly(d)` are the cadence shorthands; `gone(R)` / `gone_off(R)` the soft
  delete columns (types and sections / machines and accounts).
- `snap(db, x)` reads a row's database values with a Core SELECT (never the
  identity map); `unchanged(X)` is `snap` before the When against `snap` after
  `db.expire_all()`. `counts(db)` is "nothing written".
- `# Then N` marks the checks of the card's Then line N. Bug cards are strict
  xfails: they describe the intended behaviour and fail today on the Then line
  their card names; when the bug is fixed they XPASS, so remove the marker.

Built in normal mode (no local model).
"""
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect

from app.managers.work_order_manager import work_order_manager as wom
from app.managers.work_order_template_manager import work_order_template_manager
from app.models.account import Account
from app.models.enums import WorkOrderPriorityEnum
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.work_order_template import WorkOrderTemplateCreate as TC
from app.schemas.work_order_template import (
    WorkOrderTemplateItemCreate as IC,
)
from app.schemas.work_order_template import (
    WorkOrderTemplateItemUpdate as IU,
)
from app.schemas.work_order_template import WorkOrderTemplateUpdate as TU
from tests.unit.factories import make_profile, make_workspace

# Convention "M": the singleton manager
M = work_order_template_manager
# Conventions: MISSING, T0, D(n)
MISSING = 999999999
T0 = datetime(2026, 3, 1, 9, 0, 0)  # noqa: DTZ001 (naive UTC columns, Conventions T0)


def D(n):
    return date(2026, 3, n)


_BUGS = {
    "BUG-1015": "Work order template accepts another workspace's account, machine, section and items",
    "BUG-1228": "A soft-deleted work order type can be chosen for new work orders and templates",
    "BUG-361": "Recurring template allowed without a recurrence type",
    "BUG-362": "Out-of-range recurrence_day silently wrapped (weekly) or clamped (monthly)",
    "BUG-363": "Monthly schedule without stored day drifts after a short month",
    "BUG-2334": "Blank work order template name accepted",
    "BUG-2335": "Template approvers who cannot approve are dropped without a word",
    "BUG-2336": "Template line can be REPLACE with no replaced item",
    "BUG-2337": "Template line keeps a replaced item on a non-Replace action",
    "BUG-2338": "One item can be on a template twice",
    "BUG-2339": "Optional template fields cannot be cleared",
    "BUG-2340": "Template 'updated by' stamped when nothing changed",
    "BUG-2341": "A deleted machine, section or account can be chosen on a template",
    "BUG-2342": "Plan-day run for a section sees only the newest 1000 templates",
    "BUG-2343": "Two draft runs at once can create duplicate work orders",
    "BUG-2344": "One failing template undoes the whole Plan-day run",
    "BUG-2345": "A section's Plan day run makes drafts for recurring templates that are not due",
    "BUG-2346": "A template that requires approval but has no approvers gives orders approved at once",
    "BUG-2350": "Work order template cost and line quantity accept any number",
}


def xf(bug):
    """`xfail BUG-n` = strict xfail with the bug's title (Conventions, xfail cards)."""
    return pytest.mark.xfail(strict=True, reason=f"{bug}: {_BUGS[bug]}")


# --------------------------------------------------------------------------- #
# Standing rows (Conventions), built in every test in the stated order
# --------------------------------------------------------------------------- #

def mk(db, model, **fields):
    row = model(**fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def R(db):
    r = SimpleNamespace()
    # 1. W0 < W1 < W2
    r.W0 = make_workspace(db)
    r.W1 = make_workspace(db)
    r.W2 = make_workspace(db)
    # 2. profiles
    r.U1 = make_profile(db, name="Karim")
    r.U2 = make_profile(db, name="Rahim")
    r.U3 = make_profile(db, name="Sara")
    r.U4 = make_profile(db, name="Omar")
    r.U5 = make_profile(db, name="Nadia")
    # 3. memberships
    for ws, u, role, st in (
        (r.W1, r.U1, "manager", "active"),
        (r.W1, r.U2, "member", "active"),
        (r.W1, r.U4, "member", "suspended"),
        (r.W0, r.U5, "manager", "active"),
        (r.W2, r.U3, "manager", "active"),
    ):
        mk(db, WorkspaceMember, workspace_id=ws.id, user_id=u.id, role=role, status=st)
    # 4. types
    r.WT0 = mk(db, WorkOrderType, workspace_id=r.W0.id, name="Service")
    r.WT1 = mk(db, WorkOrderType, workspace_id=r.W1.id, name="Service")
    r.WT2 = mk(db, WorkOrderType, workspace_id=r.W1.id, name="Repair")
    r.WT9 = mk(db, WorkOrderType, workspace_id=r.W2.id, name="Service")
    # 5. factories
    r.F0 = mk(db, Factory, workspace_id=r.W0.id, name="Plant Zero", abbreviation="P0")
    r.F1 = mk(db, Factory, workspace_id=r.W1.id, name="Plant One", abbreviation="P1")
    r.F2 = mk(db, Factory, workspace_id=r.W1.id, name="Plant Two", abbreviation="P2")
    r.F9 = mk(db, Factory, workspace_id=r.W2.id, name="Plant Nine", abbreviation="P9")
    # 6. sections
    r.S0 = mk(db, FactorySection, workspace_id=r.W0.id, factory_id=r.F0.id, name="Packing")
    r.S1 = mk(db, FactorySection, workspace_id=r.W1.id, factory_id=r.F1.id, name="Packing")
    r.S2 = mk(db, FactorySection, workspace_id=r.W1.id, factory_id=r.F1.id, name="Mixing")
    r.S3 = mk(db, FactorySection, workspace_id=r.W1.id, factory_id=r.F2.id, name="Boiler")
    r.S9 = mk(db, FactorySection, workspace_id=r.W2.id, factory_id=r.F9.id, name="Packing")
    # 7. machines and section assignments
    r.M0 = mk(db, Machine, workspace_id=r.W0.id, factory_id=r.F0.id, name="Press")
    r.M1 = mk(db, Machine, workspace_id=r.W1.id, factory_id=r.F1.id, name="Press")
    r.M2 = mk(db, Machine, workspace_id=r.W1.id, factory_id=r.F1.id, name="Lathe")
    r.M3 = mk(db, Machine, workspace_id=r.W1.id, factory_id=r.F2.id, name="Pump")
    r.M9 = mk(db, Machine, workspace_id=r.W2.id, factory_id=r.F9.id, name="Press")
    for m, s in ((r.M1, r.S1), (r.M2, r.S1), (r.M3, r.S3), (r.M0, r.S0), (r.M9, r.S9)):
        mk(db, MachineSectionAssignment, workspace_id=m.workspace_id, machine_id=m.id, factory_section_id=s.id)
    # 8. items
    for key, ws, name in (("I0", r.W0, "Oil filter"), ("I1", r.W1, "Oil filter"), ("I2", r.W1, "Belt"),
                          ("I3", r.W1, "Bearing"), ("I9", r.W2, "Oil filter")):
        setattr(r, key, mk(db, Item, workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs"))
    # 9. accounts
    r.A0 = mk(db, Account, workspace_id=r.W0.id, name="Upkeep", is_active=True, is_deleted=False)
    r.A1 = mk(db, Account, workspace_id=r.W1.id, name="Upkeep", is_active=True, is_deleted=False)
    r.A9 = mk(db, Account, workspace_id=r.W2.id, name="Upkeep", is_active=True, is_deleted=False)
    return r


# --------------------------------------------------------------------------- #
# Given rows (Conventions)
# --------------------------------------------------------------------------- #

# Convention "weekly" / "daily" / "monthly(d)"
WEEKLY = {"is_recurring": True, "recurrence_type": "weekly", "recurrence_day": 0}
DAILY = {"is_recurring": True, "recurrence_type": "daily"}


def monthly(d):
    return {"is_recurring": True, "recurrence_type": "monthly", "recurrence_day": d}


def gone(R):
    """Convention "gone" (type or section)."""
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": R.U1.id}


def gone_off(R):
    """Convention "gone" (machine or account): the same plus is_active False."""
    return {**gone(R), "is_active": False}


def tpl(db, R, **over):
    """Convention "template"."""
    fields = {"workspace_id": R.W1.id, "template_name": "Oil change", "work_order_type_id": R.WT1.id,
              "created_by": R.U1.id}
    fields.update(over)
    return mk(db, WorkOrderTemplate, **fields)


def tpl_w0(db, R, **over):
    return tpl(db, R, **{"workspace_id": R.W0.id, "work_order_type_id": R.WT0.id, **over})


def tpl_w2(db, R, **over):
    return tpl(db, R, **{"workspace_id": R.W2.id, "work_order_type_id": R.WT9.id, **over})


def line(db, R, t, item, **over):
    """Convention "line(T, I)"."""
    fields = {"workspace_id": R.W1.id, "work_order_template_id": t.id, "item_id": item.id,
              "quantity": Decimal(1), "action_type": "CONSUME"}
    fields.update(over)
    return mk(db, WorkOrderTemplateItem, **fields)


def approver(db, R, t, u, **over):
    """Convention "approver(T, U)"."""
    fields = {"workspace_id": R.W1.id, "work_order_template_id": t.id, "user_id": u.id}
    fields.update(over)
    return mk(db, WorkOrderTemplateApprover, **fields)


def order(db, R, name, m, d, **over):
    """Convention "order N(m, d)"."""
    fields = {"workspace_id": R.W1.id, "work_order_number": f"WO-{name}", "title": "Service",
              "factory_id": R.F1.id, "work_order_type_id": R.WT1.id, "machine_id": m.id,
              "planned_date": d, "status": "DRAFT"}
    fields.update(over)
    return mk(db, WorkOrder, **fields)


def many_templates(db, R, n):
    """E1 ... En built with add_all (LT-05, LT-06, GD-40, GD-41)."""
    rows = [
        WorkOrderTemplate(workspace_id=R.W1.id, template_name=f"Check {k}", work_order_type_id=R.WT1.id,
                          created_by=R.U1.id, created_at=datetime(2026, 3, 1, 9, 0, 0) + timedelta(minutes=k))  # noqa: DTZ001
        for k in range(1, n + 1)
    ]
    db.add_all(rows)
    db.flush()
    return rows


# --------------------------------------------------------------------------- #
# Named checks (Conventions)
# --------------------------------------------------------------------------- #

def reread(db, model, row_id):
    """Convention "re-read X"."""
    db.expire_all()
    return db.get(model, row_id)


def _id(x):
    return sa_inspect(x).identity[0]


def snap(db, x):
    """Every column of X as stored (Core SELECT; never the identity map)."""
    table = type(x).__table__
    return dict(db.execute(select(table).where(table.c.id == _id(x))).mappings().one())


def unchanged_snap(db, x):
    """Convention "unchanged(X)": the after side, read after db.expire_all()."""
    db.expire_all()
    return snap(db, x)


_COUNTED = (WorkOrderTemplate, WorkOrderTemplateItem, WorkOrderTemplateApprover, WorkOrder)


def counts(db):
    """Convention "nothing written": row numbers of the four tables, all workspaces."""
    return tuple(db.execute(select(func.count()).select_from(m.__table__)).scalar_one() for m in _COUNTED)


def n_rows(db, model, *where):
    table = model.__table__
    return db.execute(select(func.count()).select_from(table).where(*where)).scalar_one()


def approvers(db, R, t):
    """Convention "approvers(T)"."""
    db.expire_all()
    table = WorkOrderTemplateApprover.__table__
    return list(db.execute(
        select(table.c.user_id).where(table.c.work_order_template_id == _id(t), table.c.workspace_id == R.W1.id)
        .order_by(table.c.id)
    ).scalars())


def lines(db, tpl_id):
    """Convention "lines(T)"."""
    db.expire_all()
    return (db.query(WorkOrderTemplateItem).filter(WorkOrderTemplateItem.work_order_template_id == tpl_id)
            .order_by(WorkOrderTemplateItem.id).all())


def drafts(db, tpl_id):
    """Convention "drafts(T)"."""
    db.expire_all()
    rows = db.query(WorkOrder).filter(WorkOrder.work_order_template_id == tpl_id).all()
    return sorted((o.planned_date, o.machine_id) for o in rows)


def pairs(result):
    """Convention "pairs(result)"."""
    return sorted((o.planned_date, o.machine_id) for o in result)


@contextmanager
def record_sql(db):
    """Convention "statement recorder": the SQL the session sends inside the block."""
    connection = db.connection()
    log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


def locks_of(log):
    """`locks`: recorded SELECTs naming work_order_templates with FOR UPDATE."""
    return [s for s in log if s.lstrip().upper().startswith("SELECT")
            and "work_order_templates" in s and "FOR UPDATE" in s.upper()]


ACTIVE_DETAIL = "User is not an active member of this workspace"
NEEDS_APPROVER = 'Choose at least one approver, or turn off "requires approval"'


# --------------------------------------------------------------------------- #
# _replace_approvers
# --------------------------------------------------------------------------- #

def test_wtmg_ra_01__old_approvers_replaced(db, R):
    """WTMG-RA-01 — the old approvers are replaced by the new ones, flushed, slot empty.
    Rules: _replace_approvers R1, R5, Returns."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    result = M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[R.U1.id])
    # Then 1
    assert result is None
    # Then 2
    assert not db.new
    # Then 3
    assert approvers(db, R, t) == [R.U1.id]
    # Then 4
    db.expire_all()
    row = db.query(WorkOrderTemplateApprover).filter(WorkOrderTemplateApprover.work_order_template_id == t.id).one()
    assert row.workspace_id == R.W1.id
    assert row.work_order_template_id == t.id
    assert row.user_id == R.U1.id
    # Then 5
    db.expire_all()
    row = db.query(WorkOrderTemplateApprover).filter(WorkOrderTemplateApprover.work_order_template_id == t.id).one()
    assert row.approver_slot is None


def test_wtmg_ra_02__repeated_ids_count_once(db, R):
    """WTMG-RA-02 — repeated ids count once, rows follow the order of first appearance.
    Rules: _replace_approvers R2."""
    t = tpl(db, R, requires_approval=True)
    result = M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id,
                                  approver_user_ids=[R.U2.id, R.U1.id, R.U2.id])
    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, R, t) == [R.U2.id, R.U1.id]


def test_wtmg_ra_03__empty_list_leaves_none(db, R):
    """WTMG-RA-03 — an empty list leaves no approvers.
    Rules: _replace_approvers R4."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    approver(db, R, t, R.U2)
    result = M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[])
    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, R, t) == []


def test_wtmg_ra_04__same_list_rewritten(db, R):
    """WTMG-RA-04 — the same list as stored is written again without a conflict.
    Rules: _replace_approvers R1."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    result = M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[R.U1.id])
    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, R, t) == [R.U1.id]


def test_wtmg_ra_05__other_rows_untouched(db, R):
    """WTMG-RA-05 — other templates' approvers and T's rows of another workspace are untouched.
    Rules: _replace_approvers R1."""
    s = tpl(db, R, template_name="Belt check")
    t = tpl(db, R, requires_approval=True)
    x = approver(db, R, s, R.U2)
    y = approver(db, R, t, R.U1)
    z = approver(db, R, t, R.U3, workspace_id=R.W2.id)
    before_x, before_z, y_id = snap(db, x), snap(db, z), y.id
    result = M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[R.U2.id])
    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, R, t) == [R.U2.id]
    # Then 3
    assert unchanged_snap(db, x) == before_x
    # Then 4
    assert unchanged_snap(db, z) == before_z
    # Then 5
    assert n_rows(db, WorkOrderTemplateApprover, WorkOrderTemplateApprover.__table__.c.id == y_id) == 0


@xf("BUG-2335")
def test_wtmg_ra_06__suspended_member_refused(db, R):
    """WTMG-RA-06 — a suspended member is refused, the old approvers stay.
    Rules: _replace_approvers R3 [BUG-2335]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[R.U1.id, R.U4.id])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


@xf("BUG-2335")
def test_wtmg_ra_07__invited_member_refused(db, R):
    """WTMG-RA-07 — an invited member is refused.
    Rules: _replace_approvers R3 [BUG-2335]."""
    p1 = make_profile(db, name="Lina")
    mk(db, WorkspaceMember, workspace_id=R.W1.id, user_id=p1.id, role="member", status="invited")
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[p1.id])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


@xf("BUG-2335")
def test_wtmg_ra_08__inactive_member_refused(db, R):
    """WTMG-RA-08 — a member who left (inactive) is refused.
    Rules: _replace_approvers R3 [BUG-2335]."""
    p1 = make_profile(db, name="Lina")
    mk(db, WorkspaceMember, workspace_id=R.W1.id, user_id=p1.id, role="member", status="inactive")
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[p1.id])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


@xf("BUG-2335")
def test_wtmg_ra_09__profile_without_membership_refused(db, R):
    """WTMG-RA-09 — a profile with no membership anywhere is refused.
    Rules: _replace_approvers R3 [BUG-2335]."""
    p1 = make_profile(db, name="Lina")
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[p1.id])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


@xf("BUG-2335")
@pytest.mark.parametrize("who", [
    pytest.param("U3", id="WTMG-RA-10"),
    pytest.param("U5", id="WTMG-RA-11"),
])
def test_wtmg_ra_10_11__manager_of_other_workspace_refused(db, R, who):
    """WTMG-RA-10 / RA-11 — an active manager of W2 (U3) or of W0 (U5) is refused in W1.
    Rules: _replace_approvers R3 [BUG-2335]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[getattr(R, who).id])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


@xf("BUG-2335")
def test_wtmg_ra_12__unknown_id_refused(db, R):
    """WTMG-RA-12 — an unknown id is refused.
    Rules: _replace_approvers R3 [BUG-2335]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._replace_approvers(db, tpl_id=t.id, workspace_id=R.W1.id, approver_user_ids=[R.U1.id, MISSING])
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert approvers(db, R, t) == [R.U2.id]


def test_wtmg_ra_13__flushes_never_commits(db, R):
    """WTMG-RA-13 — replacing approvers flushes and never commits.
    Rules: _replace_approvers Side effects."""
    t = tpl(db, R, requires_approval=True)
    tid = t.id
    c = WorkOrderTemplateApprover.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        M._replace_approvers(db, tpl_id=tid, workspace_id=R.W1.id, approver_user_ids=[R.U1.id])
    # Then 1
    assert n_rows(db, WorkOrderTemplateApprover, c.work_order_template_id == tid) == 1
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert n_rows(db, WorkOrderTemplateApprover, c.work_order_template_id == tid) == 0


# --------------------------------------------------------------------------- #
# create_template
# --------------------------------------------------------------------------- #

def test_wtmg_ct_01__minimal_create_defaults(db, R):
    """WTMG-CT-01 — a minimal create stores an active template of the caller's workspace with the defaults.
    Rules: create_template R1, Returns; R5 (None)."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert isinstance(result, WorkOrderTemplate)
    assert result.id is not None
    # Then 2
    assert not db.new
    rid = result.id
    # Then 3
    new = reread(db, WorkOrderTemplate, rid)
    assert new.workspace_id == R.W1.id
    assert new.template_name == "Oil change"
    assert new.work_order_type_id == R.WT1.id
    # Then 4
    new = reread(db, WorkOrderTemplate, rid)
    assert new.created_by == R.U1.id
    assert new.updated_by is None
    assert new.is_active is True
    # Then 5
    new = reread(db, WorkOrderTemplate, rid)
    assert new.priority == "MEDIUM"
    assert new.uses_inventory is False
    assert new.requires_approval is False
    assert new.is_recurring is False
    assert new.auto_generate is False
    # Then 6
    new = reread(db, WorkOrderTemplate, rid)
    assert new.cost is None
    assert new.account_id is None
    assert new.default_machine_id is None
    assert new.default_factory_section_id is None
    assert new.next_generation_date is None
    # Then 7
    assert lines(db, rid) == []
    # Then 8
    assert approvers(db, R, new) == []


def test_wtmg_ct_02__every_sent_field_stored(db, R):
    """WTMG-CT-02 — every sent field is stored as sent.
    Rules: create_template R5, R7, Returns."""
    result = M.create_template(db, data=TC(
        template_name="Belt check", work_order_type_id=R.WT2.id, description="Check belts", notes="Use gloves",
        uses_inventory=True, requires_approval=True, auto_generate=True, account_id=R.A1.id,
        cost=Decimal("120.50"), default_factory_section_id=R.S1.id, default_machine_id=R.M1.id,
        is_recurring=True, recurrence_type="weekly", recurrence_day=0, next_generation_date=D(16),
        recurrence_start_date=D(2), recurrence_end_date=D(30), approver_user_ids=[R.U2.id],
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    new = reread(db, WorkOrderTemplate, rid)
    assert new.template_name == "Belt check"
    assert new.work_order_type_id == R.WT2.id
    assert new.description == "Check belts"
    assert new.notes == "Use gloves"
    # Then 3
    new = reread(db, WorkOrderTemplate, rid)
    assert new.uses_inventory is True
    assert new.requires_approval is True
    assert new.auto_generate is True
    # Then 4
    new = reread(db, WorkOrderTemplate, rid)
    assert new.account_id == R.A1.id
    assert new.cost == Decimal("120.50")
    # Then 5
    new = reread(db, WorkOrderTemplate, rid)
    assert new.default_factory_section_id == R.S1.id
    assert new.default_machine_id == R.M1.id
    # Then 6
    new = reread(db, WorkOrderTemplate, rid)
    assert new.is_recurring is True
    assert new.recurrence_type == "weekly"
    assert new.recurrence_day == 0
    # Then 7
    new = reread(db, WorkOrderTemplate, rid)
    assert new.next_generation_date == D(16)
    assert new.recurrence_start_date == D(2)
    assert new.recurrence_end_date == D(30)
    # Then 8
    assert approvers(db, R, new) == [R.U2.id]


def test_wtmg_ct_03__type_of_w2_refused(db, R):
    """WTMG-CT-03 — a type of W2 (a later workspace) is refused, nothing written.
    Rules: create_template R1, Errors row 1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {R.WT9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert counts(db) == before






def test_wtmg_ct_04__a_type_of_w0_an_earlier(db, R):
    """WTMG-CT-04 — a type of W0 (an earlier workspace) is refused.
    Rules: create_template R1, Errors row 1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT0.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {R.WT0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_ct_05__an_unknown_type_is_refused(db, R):
    """WTMG-CT-05 — an unknown type is refused.
    Rules: create_template R1, Errors row 1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=MISSING),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order type with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1228")
def test_wtmg_ct_06__soft_deleted_type_refused(db, R):
    """WTMG-CT-06 — a soft-deleted type of the workspace is refused.
    Rules: create_template R1a [BUG-1228]."""
    wd = mk(db, WorkOrderType, workspace_id=R.W1.id, name="Old", **gone(R))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=wd.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {wd.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_11__an_account_of_w2_is_refused(db, R):
    """WTMG-CT-11 — an account of W2 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, account_id=R.A9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_12__an_account_of_w0_is_refused(db, R):
    """WTMG-CT-12 — an account of W0 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, account_id=R.A0.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_13__an_unknown_account_is_refused_as(db, R):
    """WTMG-CT-13 — an unknown account is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, account_id=MISSING),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Account with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_14__a_machine_of_w2_is_refused(db, R):
    """WTMG-CT-14 — a machine of W2 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_machine_id=R.M9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_15__a_machine_of_w0_is_refused(db, R):
    """WTMG-CT-15 — a machine of W0 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_machine_id=R.M0.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_16__a_section_of_w2_is_refused(db, R):
    """WTMG-CT-16 — a section of W2 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_factory_section_id=R.S9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {R.S9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_17__a_section_of_w0_is_refused(db, R):
    """WTMG-CT-17 — a section of W0 is refused as not found, nothing written.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_factory_section_id=R.S0.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {R.S0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_18__a_line_item_of_w2_is(db, R):
    """WTMG-CT-18 — a line item of W2 is refused, the whole create writes nothing.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True, items=[IC(item_id=R.I9.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_19__a_line_item_of_w0_is(db, R):
    """WTMG-CT-19 — a line item of W0 is refused, the whole create writes nothing.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True, items=[IC(item_id=R.I0.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_20__an_unknown_line_item_is_refused(db, R):
    """WTMG-CT-20 — an unknown line item is refused, the whole create writes nothing.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True, items=[IC(item_id=MISSING)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_21__a_replaced_item_of_w2_is(db, R):
    """WTMG-CT-21 — a replaced item of W2 is refused, the whole create writes nothing.
    Rules: create_template R3 [BUG-1015], Errors row 2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True, items=[IC(item_id=R.I1.id, action_type="REPLACE", replaced_item_id=R.I9.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2341")
def test_wtmg_ct_22__a_deleted_machine_of_the_workspace(db, R):
    """WTMG-CT-22 — a deleted machine of the workspace is refused as not found.
    Rules: create_template R3a [BUG-2341], Errors row 2."""
    mg = mk(db, Machine, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old press", **gone_off(R))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_machine_id=mg.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {mg.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2341")
def test_wtmg_ct_23__a_deleted_section_of_the_workspace(db, R):
    """WTMG-CT-23 — a deleted section of the workspace is refused as not found.
    Rules: create_template R3a [BUG-2341], Errors row 2."""
    sg = mk(db, FactorySection, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old line", **gone(R))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, default_factory_section_id=sg.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {sg.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2341")
def test_wtmg_ct_24__a_closed_account_of_the_workspace(db, R):
    """WTMG-CT-24 — a closed account of the workspace is refused as not found.
    Rules: create_template R3a [BUG-2341], Errors row 2."""
    ag = mk(db, Account, workspace_id=R.W1.id, name="Old upkeep", **gone_off(R))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id, account_id=ag.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {ag.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2334")
@pytest.mark.parametrize("name", [
    pytest.param("  ", id="WTMG-CT-07"),
    pytest.param("", id="WTMG-CT-08"),
])
def test_wtmg_ct_07_08__blank_name_rejected_by_schema(R, name):
    """WTMG-CT-07 / CT-08 — a whitespace-only or empty name is rejected by the schema.
    Rules: create_template R2 [BUG-2334]."""
    # Then 1
    with pytest.raises(ValidationError):
        TC(template_name=name, work_order_type_id=R.WT1.id)


def test_wtmg_ct_09__inner_spaces_and_capitals_kept(db, R):
    """WTMG-CT-09 — a one-letter name with inner spaces and capitals is stored as typed.
    Rules: create_template R2."""
    result = M.create_template(db, data=TC(template_name="A  Oil Check", work_order_type_id=R.WT1.id),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).template_name == "A  Oil Check"


@xf("BUG-2334")
def test_wtmg_ct_10__name_stored_trimmed(db, R):
    """WTMG-CT-10 — the name is stored trimmed.
    Rules: create_template R2 [BUG-2334]."""
    result = M.create_template(db, data=TC(template_name="  Oil change  ", work_order_type_id=R.WT1.id),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).template_name == "Oil change"


def test_wtmg_ct_25__lines_in_list_order(db, R):
    """WTMG-CT-25 — the lines are stored in list order with the template's id and workspace.
    Rules: create_template R4."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
        items=[IC(item_id=R.I2.id, quantity=Decimal(2), action_type="INSTALL", notes="Left"), IC(item_id=R.I1.id)],
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    assert len(lines(db, rid)) == 2
    # Then 3
    first = lines(db, rid)[0]
    assert first.item_id == R.I2.id
    assert first.quantity == Decimal("2.00")
    assert first.action_type == "INSTALL"
    assert first.notes == "Left"
    assert first.replaced_item_id is None
    # Then 4
    second = lines(db, rid)[1]
    assert second.item_id == R.I1.id
    assert second.quantity == Decimal("1.00")
    assert second.action_type == "CONSUME"
    assert second.notes is None
    # Then 5
    first = lines(db, rid)[0]
    assert first.workspace_id == R.W1.id
    assert first.work_order_template_id == rid
    # Then 6
    second = lines(db, rid)[1]
    assert second.workspace_id == R.W1.id
    assert second.work_order_template_id == rid


@xf("BUG-2350")
def test_wtmg_ct_26__three_decimal_line_quantity_refused_by_schema(db, R):
    """WTMG-CT-26 — a line quantity with three decimals (0.124) is refused by the schema.
    Rules: create_template R4, R9 [BUG-2350]; HR-15."""
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        IC(item_id=R.I1.id, quantity=Decimal("0.124"))
    # Then 2
    assert counts(db) == before


@xf("BUG-2350")
def test_wtmg_ct_27__negative_three_decimal_line_quantity_refused_by_schema(db, R):
    """WTMG-CT-27 — a negative line quantity with three decimals (-1.005) is refused by the schema.
    Rules: create_template R4, R9 [BUG-2350]; HR-15."""
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        IC(item_id=R.I2.id, quantity=Decimal("-1.005"))
    # Then 2
    assert counts(db) == before


def test_wtmg_ct_55__zero_and_negative_two_decimal_quantity_stored(db, R):
    """WTMG-CT-55 — a zero quantity and a negative two-decimal quantity are stored as sent.
    Rules: create_template R4, R9."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
        items=[IC(item_id=R.I1.id, quantity=Decimal(0)), IC(item_id=R.I2.id, quantity=Decimal("-1.01"))],
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [ln.quantity for ln in lines(db, result.id)] == [Decimal("0.00"), Decimal("-1.01")]


@xf("BUG-1015")
def test_wtmg_ct_56__bad_account_before_bad_section(db, R):
    """WTMG-CT-56 — check order: a bad account is reported before a bad section.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      account_id=R.A9.id, default_factory_section_id=R.S9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_57__bad_machine_before_bad_line_item(db, R):
    """WTMG-CT-57 — check order: a bad machine is reported before a bad line item.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      default_machine_id=R.M9.id, uses_inventory=True,
                                      items=[IC(item_id=R.I9.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_58__bad_machine_before_line_rule(db, R):
    """WTMG-CT-58 — check order: a bad machine is reported before a line's own rule.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      default_machine_id=R.M9.id, uses_inventory=True,
                                      items=[IC(item_id=R.I1.id, action_type="REPLACE")]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_59__line_item_before_replaced_item(db, R):
    """WTMG-CT-59 — check order: a line's item is reported before its replaced item.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      uses_inventory=True,
                                      items=[IC(item_id=R.I9.id, action_type="REPLACE", replaced_item_id=R.I0.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_60__line_item_before_own_line_rule(db, R):
    """WTMG-CT-60 — check order: a line's item is reported before its own line rule.
    Rules: create_template R10, R3, R4 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      uses_inventory=True,
                                      items=[IC(item_id=R.I9.id, action_type="REPLACE")]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_ct_28__replace_line_with_item_stored(db, R):
    """WTMG-CT-28 — a REPLACE line with its replaced item is stored.
    Rules: create_template R4."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
        items=[IC(item_id=R.I1.id, action_type="REPLACE", replaced_item_id=R.I2.id)],
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    first = lines(db, result.id)[0]
    assert first.action_type == "REPLACE"
    assert first.replaced_item_id == R.I2.id


@xf("BUG-2336")
def test_wtmg_ct_29__replace_without_item_refuses_create(db, R):
    """WTMG-CT-29 — a REPLACE line with no replaced item refuses the whole create.
    Rules: create_template R4 [BUG-2336], Errors row 3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(
            template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
            items=[IC(item_id=R.I2.id), IC(item_id=R.I1.id, action_type="REPLACE")],
        ), workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2337")
def test_wtmg_ct_30__replaced_item_on_consume_refuses_create(db, R):
    """WTMG-CT-30 — a replaced item on a CONSUME line refuses the create.
    Rules: create_template R4 [BUG-2337], Errors row 3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(
            template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
            items=[IC(item_id=R.I1.id, replaced_item_id=R.I2.id)],
        ), workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "replaced_item_id only applies to Replace"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2338")
def test_wtmg_ct_31__same_item_twice_refused_409(db, R):
    """WTMG-CT-31 — the same item twice refuses the create with 409.
    Rules: create_template R4 [BUG-2338], Errors row 3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(
            template_name="Oil change", work_order_type_id=R.WT1.id, uses_inventory=True,
            items=[IC(item_id=R.I1.id), IC(item_id=R.I2.id), IC(item_id=R.I1.id, quantity=Decimal(3))],
        ), workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Oil filter is already on this template"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_ct_32__approvers_in_order_sent(db, R):
    """WTMG-CT-32 — approvers are stored in the order sent.
    Rules: create_template R5."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           requires_approval=True, approver_user_ids=[R.U2.id, R.U1.id]),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert approvers(db, R, result) == [R.U2.id, R.U1.id]


def test_wtmg_ct_33__empty_approver_list_stores_none(db, R):
    """WTMG-CT-33 — an empty approver list stores none.
    Rules: create_template R5."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           approver_user_ids=[]),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert approvers(db, R, result) == []


@xf("BUG-2335")
def test_wtmg_ct_34__suspended_approver_refuses_before_writing(db, R):
    """WTMG-CT-34 — a suspended approver refuses the create before anything is written.
    Rules: create_template R5 [BUG-2335], Errors row 4."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(
            template_name="Oil change", work_order_type_id=R.WT1.id, requires_approval=True, uses_inventory=True,
            items=[IC(item_id=R.I1.id)], approver_user_ids=[R.U1.id, R.U4.id],
        ), workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert counts(db) == before


def test_wtmg_ct_35__lines_stored_without_uses_inventory(db, R):
    """WTMG-CT-35 — lines are stored even when uses_inventory is false.
    Rules: create_template R8."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           uses_inventory=False, items=[IC(item_id=R.I1.id)]),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    assert reread(db, WorkOrderTemplate, rid).uses_inventory is False
    # Then 3
    assert [ln.item_id for ln in lines(db, rid)] == [R.I1.id]


@xf("BUG-2350")
@pytest.mark.parametrize("cost", [
    pytest.param("0.125", id="WTMG-CT-36"),
    pytest.param("0.124", id="WTMG-CT-37"),
    pytest.param("2.345", id="WTMG-CT-38"),
    pytest.param("-1.005", id="WTMG-CT-39"),
    pytest.param("10000000000000", id="WTMG-CT-47"),
])
def test_wtmg_ct_36_39_47__cost_out_of_range_refused_by_schema(db, R, cost):
    """WTMG-CT-36 … CT-39, CT-47 — a cost with three decimals or 14 integer digits is refused by the schema.
    Rules: create_template R9 [BUG-2350]; HR-15."""
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        TC(template_name="Oil change", work_order_type_id=R.WT1.id, cost=Decimal(cost))
    # Then 2
    assert counts(db) == before


@pytest.mark.parametrize(("cost", "stored"), [
    pytest.param("0", "0.00", id="WTMG-CT-40"),
    pytest.param("9999999999999.99", "9999999999999.99", id="WTMG-CT-41"),
    pytest.param("0.01", "0.01", id="WTMG-CT-48"),
])
def test_wtmg_ct_40_41_48__cost_in_range_stored_exactly(db, R, cost, stored):
    """WTMG-CT-40, CT-41, CT-48 — cost 0, the largest Numeric(15, 2) value and the smallest step are stored exactly.
    Rules: create_template Returns, R9; HR-15."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           cost=Decimal(cost)),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).cost == Decimal(stored)


@xf("BUG-363")
def test_wtmg_ct_42__monthly_without_day_takes_start_day(db, R):
    """WTMG-CT-42 — a monthly template with no day takes the day of its start date.
    Rules: create_template R7; recurrence R8a [BUG-363]."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, is_recurring=True, recurrence_type="monthly",
        recurrence_start_date=date(2026, 1, 31), next_generation_date=date(2026, 2, 28),
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).recurrence_day == 31


@xf("BUG-363")
def test_wtmg_ct_43__monthly_without_day_or_start_takes_next_day(db, R):
    """WTMG-CT-43 — a monthly template with no day and no start takes the day of its next date.
    Rules: create_template R7; recurrence R8a [BUG-363]."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, is_recurring=True, recurrence_type="monthly",
        next_generation_date=date(2026, 2, 15),
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).recurrence_day == 15


def test_wtmg_ct_44__monthly_without_day_or_dates_keeps_none(db, R):
    """WTMG-CT-44 — a monthly template with no day and no dates keeps no day.
    Rules: create_template R7; recurrence R8a."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           is_recurring=True, recurrence_type="monthly"),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).recurrence_day is None


def test_wtmg_ct_45__explicit_monthly_day_kept(db, R):
    """WTMG-CT-45 — an explicit monthly day is kept, not taken from the start date.
    Rules: create_template R7; recurrence R8a."""
    result = M.create_template(db, data=TC(
        template_name="Oil change", work_order_type_id=R.WT1.id, is_recurring=True, recurrence_type="monthly",
        recurrence_day=10, recurrence_start_date=date(2026, 1, 31),
    ), workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplate, result.id).recurrence_day == 10


def test_wtmg_ct_46__create_flushes_never_commits(db, R):
    """WTMG-CT-46 — create flushes and never commits.
    Rules: create_template Side effects."""
    c = WorkOrderTemplate.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.create_template(db, data=TC(template_name="Rolled back", work_order_type_id=R.WT1.id,
                                               uses_inventory=True, items=[IC(item_id=R.I1.id)]),
                                   workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert n_rows(db, WorkOrderTemplate, c.template_name == "Rolled back") == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrderTemplate, c.template_name == "Rolled back") == 0


def test_wtmg_ct_49__priority_and_assignee_stored(db, R):
    """WTMG-CT-49 — priority and the free-text assignee are stored as sent.
    Rules: create_template Returns (spec Facts, G5)."""
    result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                           priority=WorkOrderPriorityEnum.HIGH, assigned_to="Karim"),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    new = reread(db, WorkOrderTemplate, result.id)
    assert new.priority == "HIGH"
    assert new.assigned_to == "Karim"


@xf("BUG-1015")
def test_wtmg_ct_50__bad_account_before_bad_machine(db, R):
    """WTMG-CT-50 — check order: a bad account is reported before a bad machine.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      account_id=R.A9.id, default_machine_id=R.M9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_51__bad_section_before_bad_machine(db, R):
    """WTMG-CT-51 — check order: a bad section is reported before a bad machine.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      default_factory_section_id=R.S9.id, default_machine_id=R.M9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {R.S9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_ct_52__bad_type_before_bad_account(db, R):
    """WTMG-CT-52 — check order: a bad type is reported before a bad account.
    Rules: create_template R10, R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT9.id,
                                      account_id=R.A9.id),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {R.WT9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-1015")
def test_wtmg_ct_53__bad_line_item_before_suspended_approver(db, R):
    """WTMG-CT-53 — check order: a bad line item is reported before a suspended approver.
    Rules: create_template R10, R3 [BUG-1015]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      requires_approval=True, uses_inventory=True,
                                      items=[IC(item_id=R.I9.id)], approver_user_ids=[R.U4.id]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2336")
def test_wtmg_ct_54__first_line_rule_before_second_line_item(db, R):
    """WTMG-CT-54 — check order: the first line's rule is reported before the second line's item.
    Rules: create_template R10, R4 [BUG-2336]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=R.WT1.id,
                                      uses_inventory=True,
                                      items=[IC(item_id=R.I1.id, action_type="REPLACE"), IC(item_id=R.I9.id)]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# update_template
# --------------------------------------------------------------------------- #

def test_wtmg_ut_01__sent_field_changed_and_stamped(db, R):
    """WTMG-UT-01 — a sent field is changed and the template is stamped.
    Rules: update_template R5, R10, Returns."""
    t = tpl(db, R, description="Old")
    result = M.update_template(db, tpl_id=t.id, data=TU(description="New"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.description == "New"
    assert row.template_name == "Oil change"
    # Then 3
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by == R.U2.id
    assert row.updated_at is not None
    assert row.created_by == R.U1.id


def test_wtmg_ut_05__inactive_template_updated_stays_inactive(db, R):
    """WTMG-UT-05 — an inactive template can be updated and stays inactive.
    Rules: update_template R2."""
    t = tpl(db, R, is_active=False)
    result = M.update_template(db, tpl_id=t.id, data=TU(notes="Checked"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.notes == "Checked"
    assert row.is_active is False


def test_wtmg_ut_06__is_active_true_restores(db, R):
    """WTMG-UT-06 — is_active true restores an inactive template.
    Rules: update_template R2."""
    t = tpl(db, R, is_active=False)
    result = M.update_template(db, tpl_id=t.id, data=TU(is_active=True), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.is_active is True
    assert row.updated_by == R.U2.id


def test_wtmg_ut_07__is_active_false_deactivates(db, R):
    """WTMG-UT-07 — is_active false deactivates an active template.
    Rules: update_template R2."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(is_active=False), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.is_active is False
    assert row.updated_by == R.U2.id


def test_wtmg_ut_08__other_type_of_workspace_stored(db, R):
    """WTMG-UT-08 — another type of the workspace is stored.
    Rules: update_template R3."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=R.WT2.id), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).work_order_type_id == R.WT2.id


def test_wtmg_ut_13__current_deleted_type_accepted_when_resent(db, R):
    """WTMG-UT-13 — the current type, deleted meanwhile, is accepted when re-sent.
    Rules: update_template R3."""
    wd = mk(db, WorkOrderType, workspace_id=R.W1.id, name="Old", **gone(R))
    t = tpl(db, R, work_order_type_id=wd.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=wd.id, notes="Kept"),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.work_order_type_id == wd.id
    assert row.notes == "Kept"


@xf("BUG-2334")
def test_wtmg_ut_14__name_stored_trimmed(db, R):
    """WTMG-UT-14 — the name is stored trimmed.
    Rules: update_template R4 [BUG-2334]."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(template_name="  Pump check  "), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).template_name == "Pump check"


@xf("BUG-2334")
def test_wtmg_ut_15__whitespace_name_rejected_by_schema(db, R):
    """WTMG-UT-15 — a whitespace-only name is rejected by the schema.
    Rules: update_template R4 [BUG-2334]."""
    tpl(db, R)
    # Then 1
    with pytest.raises(ValidationError):
        TU(template_name="  ")


def test_wtmg_ut_16__fields_not_sent_left_alone(db, R):
    """WTMG-UT-16 — fields not sent are left as they are.
    Rules: update_template R5."""
    t = tpl(db, R, description="Old", notes="Keep", cost=Decimal("5.00"), account_id=R.A1.id,
            default_machine_id=R.M1.id, priority="MEDIUM")
    result = M.update_template(db, tpl_id=t.id, data=TU(description="New"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).description == "New"
    # Then 3
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.notes == "Keep"
    assert row.cost == Decimal("5.00")
    assert row.account_id == R.A1.id
    assert row.default_machine_id == R.M1.id
    assert row.priority == "MEDIUM"
    assert row.template_name == "Oil change"


@xf("BUG-2339")
def test_wtmg_ut_17__null_clears_description(db, R):
    """WTMG-UT-17 — an explicit null clears description.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, description="Old")
    result = M.update_template(db, tpl_id=t.id, data=TU(description=None), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).description is None


@xf("BUG-2339")
def test_wtmg_ut_18__null_clears_cost(db, R):
    """WTMG-UT-18 — an explicit null clears cost.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, cost=Decimal("5.00"))
    result = M.update_template(db, tpl_id=t.id, data=TU(cost=None), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).cost is None


@xf("BUG-2339")
def test_wtmg_ut_19__null_clears_account(db, R):
    """WTMG-UT-19 — an explicit null clears account_id.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, account_id=R.A1.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(account_id=None), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).account_id is None


@xf("BUG-2339")
def test_wtmg_ut_20__null_clears_default_machine(db, R):
    """WTMG-UT-20 — an explicit null clears default_machine_id.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, default_machine_id=R.M1.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(default_machine_id=None), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).default_machine_id is None


@xf("BUG-2339")
def test_wtmg_ut_21__null_clears_next_generation_date(db, R):
    """WTMG-UT-21 — an explicit null clears next_generation_date.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, next_generation_date=D(16))
    result = M.update_template(db, tpl_id=t.id, data=TU(next_generation_date=None), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date is None


@xf("BUG-2339")
def test_wtmg_ut_22__nulls_clear_notes_range_and_section(db, R):
    """WTMG-UT-22 — explicit nulls clear notes, the range dates and the section.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, notes="Keep", recurrence_start_date=D(2), recurrence_end_date=D(30),
            default_factory_section_id=R.S1.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(notes=None, recurrence_start_date=None,
                                                         recurrence_end_date=None, default_factory_section_id=None),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.notes is None
    assert row.recurrence_start_date is None
    assert row.recurrence_end_date is None
    assert row.default_factory_section_id is None


@xf("BUG-2339")
def test_wtmg_ut_23__nulls_clear_type_and_day_of_non_recurring(db, R):
    """WTMG-UT-23 — explicit nulls clear the type and day of a non-recurring template.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, recurrence_type="daily", recurrence_day=3)
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_type=None, recurrence_day=None),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.recurrence_type is None
    assert row.recurrence_day is None


@xf("BUG-2339")
@pytest.mark.parametrize("field", [
    pytest.param("template_name", id="WTMG-UT-24"),
    pytest.param("work_order_type_id", id="WTMG-UT-25"),
    pytest.param("priority", id="WTMG-UT-26"),
    pytest.param("uses_inventory", id="WTMG-UT-27"),
    pytest.param("requires_approval", id="WTMG-UT-28"),
    pytest.param("is_active", id="WTMG-UT-29"),
    pytest.param("is_recurring", id="WTMG-UT-30"),
    pytest.param("auto_generate", id="WTMG-UT-31"),
])
def test_wtmg_ut_24_31__null_for_required_field_rejected(db, R, field):
    """WTMG-UT-24 … UT-31 — null for a required template field is rejected by the schema.
    Rules: update_template R5 [BUG-2339]."""
    tpl(db, R)
    # Then 1
    with pytest.raises(ValidationError):
        TU(**{field: None})


def test_wtmg_ut_42__current_deleted_machine_accepted(db, R):
    """WTMG-UT-42 — a deleted machine already on the template is accepted when re-sent.
    Rules: update_template R6a."""
    mg = mk(db, Machine, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old press", **gone_off(R))
    t = tpl(db, R, default_machine_id=mg.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(default_machine_id=mg.id, notes="Kept"),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.default_machine_id == mg.id
    assert row.notes == "Kept"


def test_wtmg_ut_43__current_deleted_section_accepted(db, R):
    """WTMG-UT-43 — a deleted section already on the template is accepted when re-sent.
    Rules: update_template R6a."""
    sg = mk(db, FactorySection, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old line", **gone(R))
    t = tpl(db, R, default_factory_section_id=sg.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(default_factory_section_id=sg.id, notes="Kept"),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.default_factory_section_id == sg.id
    assert row.notes == "Kept"


def test_wtmg_ut_44__current_closed_account_accepted(db, R):
    """WTMG-UT-44 — a closed account already on the template is accepted when re-sent.
    Rules: update_template R6a."""
    ag = mk(db, Account, workspace_id=R.W1.id, name="Old upkeep", **gone_off(R))
    t = tpl(db, R, account_id=ag.id)
    result = M.update_template(db, tpl_id=t.id, data=TU(account_id=ag.id, notes="Kept"),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.account_id == ag.id
    assert row.notes == "Kept"


def test_wtmg_ut_47__weekly_day_6_accepted(db, R):
    """WTMG-UT-47 — a weekly day of 6 is accepted.
    Rules: update_template R7; recurrence R4a."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=6), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == 6


@pytest.mark.parametrize("day", [
    pytest.param(31, id="WTMG-UT-51"),
    pytest.param(1, id="WTMG-UT-52"),
])
def test_wtmg_ut_51_52__monthly_day_at_bounds_accepted(db, R, day):
    """WTMG-UT-51 / UT-52 — a monthly day of 31 or 1 is accepted.
    Rules: update_template R7; recurrence R7a."""
    t = tpl(db, R, **monthly(15), next_generation_date=D(16))
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=day), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == day


def test_wtmg_ut_56__non_recurring_keeps_null_type(db, R):
    """WTMG-UT-56 — a non-recurring template keeps a null type on another update.
    Rules: update_template R7; recurrence R11b."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(notes="Checked"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.recurrence_type is None
    assert row.notes == "Checked"


def test_wtmg_ut_57__daily_accepts_day_45(db, R):
    """WTMG-UT-57 — a daily template accepts day 45 and keeps it.
    Rules: update_template R7; recurrence R10a."""
    t = tpl(db, R, **DAILY, next_generation_date=D(16))
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=45), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == 45


def test_wtmg_ut_58__untyped_non_recurring_accepts_day_minus_1(db, R):
    """WTMG-UT-58 — a non-recurring untyped template accepts day -1 and keeps it.
    Rules: update_template R7; recurrence R10a."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=-1), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == -1


@xf("BUG-363")
def test_wtmg_ut_59__monthly_without_day_gets_start_day_on_update(db, R):
    """WTMG-UT-59 — a monthly template with no day gets the day of its start date on update.
    Rules: update_template R7; recurrence R8a [BUG-363]."""
    t = tpl(db, R, is_recurring=True, recurrence_type="monthly", recurrence_start_date=date(2026, 1, 31),
            next_generation_date=date(2026, 2, 28))
    result = M.update_template(db, tpl_id=t.id, data=TU(notes="Checked"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == 31


@xf("BUG-363")
def test_wtmg_ut_60__daily_to_monthly_takes_next_date_day(db, R):
    """WTMG-UT-60 — a daily template changed to monthly with no start takes the day of its next date.
    Rules: update_template R7; recurrence R8a [BUG-363]."""
    t = tpl(db, R, **DAILY, next_generation_date=date(2026, 2, 15))
    result = M.update_template(db, tpl_id=t.id, data=TU(recurrence_type="monthly"), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day == 15


def test_wtmg_ut_61__sent_approvers_replace_old(db, R):
    """WTMG-UT-61 — sent approvers replace the old ones, in the order sent.
    Rules: update_template R8."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    result = M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=[R.U2.id, R.U1.id]),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert approvers(db, R, t) == [R.U2.id, R.U1.id]


def test_wtmg_ut_62__approvers_not_sent_untouched(db, R):
    """WTMG-UT-62 — approvers not sent are untouched.
    Rules: update_template R8."""
    t = tpl(db, R, requires_approval=True)
    x = approver(db, R, t, R.U1)
    before_x = snap(db, x)
    result = M.update_template(db, tpl_id=t.id, data=TU(notes="Checked"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert approvers(db, R, t) == [R.U1.id]
    # Then 3
    assert unchanged_snap(db, x) == before_x


@pytest.mark.parametrize("sent", [
    pytest.param(None, id="WTMG-UT-63"),
    pytest.param([], id="WTMG-UT-64"),
])
def test_wtmg_ut_63_64__null_or_empty_approvers_remove_all(db, R, sent):
    """WTMG-UT-63 / UT-64 — approvers sent as null or as an empty list remove all.
    Rules: update_template R8."""
    t = tpl(db, R)
    approver(db, R, t, R.U1)
    result = M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=sent), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert approvers(db, R, t) == []


@xf("BUG-2335")
def test_wtmg_ut_65__suspended_approver_refused_old_stay(db, R):
    """WTMG-UT-65 — a suspended approver is refused and the old approvers stay.
    Rules: update_template R8 [BUG-2335]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=[R.U4.id]), workspace_id=R.W1.id,
                          user_id=R.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert approvers(db, R, t) == [R.U1.id]


def test_wtmg_ut_66__empty_update_changes_no_field(db, R):
    """WTMG-UT-66 — an empty update returns the template and changes no field.
    Rules: update_template R5, Returns."""
    t = tpl(db, R, description="Old")
    result = M.update_template(db, tpl_id=t.id, data=TU(), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.description == "Old"
    assert row.template_name == "Oil change"
    assert row.is_active is True


@xf("BUG-2340")
def test_wtmg_ut_67__empty_update_writes_no_stamp(db, R):
    """WTMG-UT-67 — an empty update writes no stamp.
    Rules: update_template R10 [BUG-2340]."""
    t = tpl(db, R, description="Old")
    result = M.update_template(db, tpl_id=t.id, data=TU(), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by is None
    assert row.updated_at is None


@xf("BUG-2340")
def test_wtmg_ut_68__resent_value_writes_no_stamp(db, R):
    """WTMG-UT-68 — re-sending the stored value writes no stamp.
    Rules: update_template R10 [BUG-2340]."""
    t = tpl(db, R, description="Old")
    result = M.update_template(db, tpl_id=t.id, data=TU(description="Old"), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by is None
    assert row.updated_at is None


@xf("BUG-2340")
def test_wtmg_ut_69__same_approver_set_writes_no_stamp(db, R):
    """WTMG-UT-69 — re-sending the same approver set writes no stamp.
    Rules: update_template R10 [BUG-2340]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    result = M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=[R.U1.id]), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by is None
    assert row.updated_at is None


def test_wtmg_ut_70__approver_change_alone_stamps(db, R):
    """WTMG-UT-70 — a change of the approver set alone stamps the template.
    Rules: update_template R10."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    result = M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=[R.U2.id]), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).updated_by == R.U2.id
    # Then 3
    assert approvers(db, R, t) == [R.U2.id]


def test_wtmg_ut_71__lines_not_touched(db, R):
    """WTMG-UT-71 — the template's lines are not touched.
    Rules: update_template R11."""
    t = tpl(db, R, uses_inventory=True)
    ln = line(db, R, t, R.I1)
    before_l = snap(db, ln)
    result = M.update_template(db, tpl_id=t.id, data=TU(uses_inventory=False), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).uses_inventory is False
    # Then 3
    assert unchanged_snap(db, ln) == before_l


@xf("BUG-2350")
@pytest.mark.parametrize("cost", [
    pytest.param("0.125", id="WTMG-UT-72"),
    pytest.param("2.345", id="WTMG-UT-73"),
    pytest.param("10000000000000", id="WTMG-UT-76"),
])
def test_wtmg_ut_72_73_76__sent_cost_out_of_range_refused_by_schema(db, R, cost):
    """WTMG-UT-72, UT-73, UT-76 — a sent cost with three decimals or 14 integer digits is refused by the schema.
    Rules: update_template R5a [BUG-2350]; HR-15."""
    tpl(db, R, cost=Decimal("5.00"))
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        TU(cost=Decimal(cost))
    # Then 2
    assert counts(db) == before


def test_wtmg_ut_74__cost_zero_replaces_old(db, R):
    """WTMG-UT-74 — cost 0 is stored as 0.00 (zero is a value and replaces 5.00).
    Rules: update_template R5; HR-15."""
    t = tpl(db, R, cost=Decimal("5.00"))
    result = M.update_template(db, tpl_id=t.id, data=TU(cost=Decimal(0)), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).cost == Decimal("0.00")


def test_wtmg_ut_75__update_flushes_never_commits(db, R):
    """WTMG-UT-75 — update flushes and never commits.
    Rules: update_template Side effects."""
    t = tpl(db, R, description="Old")
    tid = t.id
    c = WorkOrderTemplate.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.update_template(db, tpl_id=tid, data=TU(description="New"), workspace_id=R.W1.id,
                                   user_id=R.U2.id)
    # Then 1
    assert result.id == tid
    # Then 2
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.description == "New") == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.description == "New") == 0


@xf("BUG-2339")
def test_wtmg_ut_77__null_clears_assignee(db, R):
    """WTMG-UT-77 — an explicit null clears the free-text assignee.
    Rules: update_template R5 [BUG-2339]."""
    t = tpl(db, R, assigned_to="Karim")
    result = M.update_template(db, tpl_id=t.id, data=TU(assigned_to=None), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).assigned_to is None


@xf("BUG-2335")
def test_wtmg_ut_78__suspended_approver_refused_before_field_written(db, R):
    """WTMG-UT-78 — a suspended approver is refused before any field is written.
    Rules: update_template R8 [BUG-2335]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(template_name="Belt check", approver_user_ids=[R.U1.id, R.U4.id]),
                          workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert t.template_name == "Oil change"
    assert t.updated_by is None
    # Then 6
    assert unchanged_snap(db, t) == before
    # Then 7
    assert approvers(db, R, t) == [R.U1.id]


def test_wtmg_ut_02__unknown_id_refused(db, R):
    """WTMG-UT-02 — an unknown id is refused, nothing changes.
    Rules: update_template R1."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=MISSING, data=TU(description="New"), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


def test_wtmg_ut_03__template_of_w2_refused(db, R):
    """WTMG-UT-03 — a template of W2 (a later row) is refused in W1.
    Rules: update_template R1."""
    tpl(db, R)
    z = tpl_w2(db, R)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=z.id, data=TU(description="New"), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, z) == before


def test_wtmg_ut_04__template_of_w0_refused(db, R):
    """WTMG-UT-04 — a template of W0 (an earlier row) is refused in W1.
    Rules: update_template R1."""
    z = tpl_w0(db, R)
    tpl(db, R)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=z.id, data=TU(description="New"), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, z) == before


def test_wtmg_ut_09__type_of_w2_refused(db, R):
    """WTMG-UT-09 — a type of W2 is refused, nothing changes.
    Rules: update_template R3."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=R.WT9.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {R.WT9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


def test_wtmg_ut_10__type_of_w0_refused(db, R):
    """WTMG-UT-10 — a type of W0 is refused, nothing changes.
    Rules: update_template R3."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=R.WT0.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {R.WT0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


def test_wtmg_ut_11__unknown_type_refused(db, R):
    """WTMG-UT-11 — an unknown type is refused.
    Rules: update_template R3."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=MISSING), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order type with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1228")
def test_wtmg_ut_12__deleted_type_not_current_refused(db, R):
    """WTMG-UT-12 — a soft-deleted type that is not the current one is refused.
    Rules: update_template R3 [BUG-1228]."""
    wd = mk(db, WorkOrderType, workspace_id=R.W1.id, name="Old", **gone(R))
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(work_order_type_id=wd.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order type with ID {wd.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_32__account_of_w2_refused(db, R):
    """WTMG-UT-32 — an account of W2 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(account_id=R.A9.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_33__account_of_w0_refused(db, R):
    """WTMG-UT-33 — an account of W0 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(account_id=R.A0.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {R.A0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_34__machine_of_w2_refused(db, R):
    """WTMG-UT-34 — a machine of W2 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_machine_id=R.M9.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_35__machine_of_w0_refused(db, R):
    """WTMG-UT-35 — a machine of W0 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_machine_id=R.M0.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_36__section_of_w2_refused(db, R):
    """WTMG-UT-36 — a section of W2 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_factory_section_id=R.S9.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {R.S9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_37__section_of_w0_refused(db, R):
    """WTMG-UT-37 — a section of W0 is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_factory_section_id=R.S0.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {R.S0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-1015")
def test_wtmg_ut_38__unknown_account_refused(db, R):
    """WTMG-UT-38 — an unknown account is refused, nothing changes.
    Rules: update_template R6 [BUG-1015]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(account_id=MISSING), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Account with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-2341")
def test_wtmg_ut_39__deleted_machine_not_current_refused(db, R):
    """WTMG-UT-39 — a deleted machine that is not the current one is refused.
    Rules: update_template R6a [BUG-2341]."""
    mg = mk(db, Machine, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old press", **gone_off(R))
    t = tpl(db, R, default_machine_id=R.M1.id)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_machine_id=mg.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {mg.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-2341")
def test_wtmg_ut_40__deleted_section_not_current_refused(db, R):
    """WTMG-UT-40 — a deleted section that is not the current one is refused.
    Rules: update_template R6a [BUG-2341]."""
    sg = mk(db, FactorySection, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old line", **gone(R))
    t = tpl(db, R, default_factory_section_id=R.S1.id)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(default_factory_section_id=sg.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory section with ID {sg.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-2341")
def test_wtmg_ut_41__closed_account_not_current_refused(db, R):
    """WTMG-UT-41 — a closed account that is not the current one is refused.
    Rules: update_template R6a [BUG-2341]."""
    ag = mk(db, Account, workspace_id=R.W1.id, name="Old upkeep", **gone_off(R))
    t = tpl(db, R, account_id=R.A1.id)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(account_id=ag.id), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {ag.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_45__weekly_day_7_refused(db, R):
    """WTMG-UT-45 — a weekly day of 7 is refused.
    Rules: update_template R7; recurrence R4a [BUG-362]."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=7), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Weekly recurrence day must be between 0 and 6"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_46__weekly_day_minus_1_refused(db, R):
    """WTMG-UT-46 — a weekly day of -1 is refused.
    Rules: update_template R7; recurrence R4a [BUG-362]."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=-1), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Weekly recurrence day must be between 0 and 6"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_48__stored_day_9_invalid_for_weekly(db, R):
    """WTMG-UT-48 — a stored day 9 becomes invalid when the type is changed to weekly (merged state).
    Rules: update_template R7; recurrence R4a [BUG-362]."""
    t = tpl(db, R, **DAILY, recurrence_day=9, next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_type="weekly"), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Weekly recurrence day must be between 0 and 6"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_49__monthly_day_0_refused(db, R):
    """WTMG-UT-49 — a monthly day of 0 is refused.
    Rules: update_template R7; recurrence R7a [BUG-362]."""
    t = tpl(db, R, **monthly(15), next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=0), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Monthly recurrence day must be between 1 and 31"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_50__monthly_day_32_refused(db, R):
    """WTMG-UT-50 — a monthly day of 32 is refused.
    Rules: update_template R7; recurrence R7a [BUG-362]."""
    t = tpl(db, R, **monthly(15), next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_day=32), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Monthly recurrence day must be between 1 and 31"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-362")
def test_wtmg_ut_53__stored_day_45_invalid_for_monthly(db, R):
    """WTMG-UT-53 — a stored day 45 becomes invalid when the type is changed to monthly (merged state).
    Rules: update_template R7; recurrence R7a [BUG-362]."""
    t = tpl(db, R, **DAILY, recurrence_day=45, next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_type="monthly"), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Monthly recurrence day must be between 1 and 31"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-361")
def test_wtmg_ut_54__recurring_without_type_refused(db, R):
    """WTMG-UT-54 — turning a template with no type recurring is refused.
    Rules: update_template R7; recurrence R11b [BUG-361]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(is_recurring=True), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "A recurring template needs a recurrence type"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@xf("BUG-361")
def test_wtmg_ut_55__clearing_type_of_recurring_refused(db, R):
    """WTMG-UT-55 — clearing the type of a recurring template is refused.
    Rules: update_template R7; recurrence R11b [BUG-361]."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(recurrence_type=None), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "A recurring template needs a recurrence type"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged_snap(db, t) == before


@pytest.mark.parametrize("cost", [
    pytest.param("9999999999999.99", id="WTMG-UT-79"),
    pytest.param("0.01", id="WTMG-UT-80"),
])
def test_wtmg_ut_79_80__cost_at_bounds_stored_exactly(db, R, cost):
    """WTMG-UT-79 / UT-80 — the largest cost (9999999999999.99) and the smallest step (0.01) are stored exactly.
    Rules: update_template R5a (BUG-2350 bounds, accepted)."""
    t = tpl(db, R, cost=Decimal("5.00"))
    result = M.update_template(db, tpl_id=t.id, data=TU(cost=Decimal(cost)), workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).cost == Decimal(cost)


# --------------------------------------------------------------------------- #
# get_template
# --------------------------------------------------------------------------- #

def test_wtmg_gt_01__returns_workspace_template(db, R):
    """WTMG-GT-01 — returns the workspace's template.
    Rules: get_template R1."""
    tpl(db, R, template_name="Belt check")
    t = tpl(db, R)
    result = M.get_template(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert isinstance(result, WorkOrderTemplate)
    assert result.id == t.id
    assert result.template_name == "Oil change"


def test_wtmg_gt_02__inactive_template_returned(db, R):
    """WTMG-GT-02 — an inactive template is returned.
    Rules: get_template R1."""
    t = tpl(db, R, is_active=False)
    result = M.get_template(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert result.id == t.id
    assert result.is_active is False


def test_wtmg_gt_03__unknown_id_404(db, R):
    """WTMG-GT-03 — an unknown id is 404.
    Rules: get_template R2."""
    tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=MISSING, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template with ID 999999999 not found"


def test_wtmg_gt_04__template_of_w2_404(db, R):
    """WTMG-GT-04 — a template of W2 (a later row) is 404 in W1.
    Rules: get_template R2."""
    tpl(db, R)
    z = tpl_w2(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=z.id, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"


def test_wtmg_gt_05__template_of_w0_404(db, R):
    """WTMG-GT-05 — a template of W0 (an earlier row) is 404 in W1.
    Rules: get_template R2."""
    z = tpl_w0(db, R)
    tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=z.id, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"


def test_wtmg_gt_06__w1_template_under_w2_404(db, R):
    """WTMG-GT-06 — W1's template asked for under W2 is 404.
    Rules: get_template R2."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=t.id, workspace_id=R.W2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {t.id} not found"


def test_wtmg_gt_07__writes_nothing(db, R):
    """WTMG-GT-07 — writes nothing: a pending row and an unflushed edit stay as they were.
    Rules: get_template R1."""
    t = tpl(db, R)
    s = tpl(db, R, template_name="Belt check")
    s.notes = "Edited"
    p = WorkOrderTemplate(workspace_id=R.W1.id, template_name="Pending", work_order_type_id=R.WT1.id)
    db.add(p)
    result = M.get_template(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert s in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# list_templates
# --------------------------------------------------------------------------- #

def _at(day):
    return datetime(2026, 3, day, 9, 0, 0)  # noqa: DTZ001


def test_wtmg_lt_01__defaults_newest_first_active_and_inactive(db, R):
    """WTMG-LT-01 — with the defaults: the workspace's templates newest first, active and inactive.
    Rules: list_templates R1."""
    tpl_w0(db, R, created_at=_at(9))
    t1 = tpl(db, R, created_at=_at(2))
    t2 = tpl(db, R, created_at=_at(4), is_active=False)
    t3 = tpl(db, R, created_at=_at(3))
    tpl_w2(db, R, created_at=_at(9))
    result = M.list_templates(db, workspace_id=R.W1.id)
    # Then 1
    assert [t.id for t in result] == [t2.id, t3.id, t1.id]


def test_wtmg_lt_02__is_active_passed_through(db, R):
    """WTMG-LT-02 — is_active is passed through.
    Rules: list_templates R1."""
    tpl(db, R, created_at=_at(2))
    t2 = tpl(db, R, created_at=_at(4), is_active=False)
    tpl(db, R, created_at=_at(3))
    result = M.list_templates(db, workspace_id=R.W1.id, is_active=False)
    # Then 1
    assert [t.id for t in result] == [t2.id]


def test_wtmg_lt_03__type_passed_through(db, R):
    """WTMG-LT-03 — work_order_type_id is passed through.
    Rules: list_templates R1."""
    tpl(db, R, created_at=_at(2))
    t2 = tpl(db, R, created_at=_at(4), work_order_type_id=R.WT2.id)
    tpl(db, R, created_at=_at(3))
    result = M.list_templates(db, workspace_id=R.W1.id, work_order_type_id=R.WT2.id)
    # Then 1
    assert [t.id for t in result] == [t2.id]


def test_wtmg_lt_04__skip_and_limit_passed_through(db, R):
    """WTMG-LT-04 — skip and limit are passed through.
    Rules: list_templates R1."""
    tpl(db, R, created_at=_at(2))
    tpl(db, R, created_at=_at(4))
    t3 = tpl(db, R, created_at=_at(3))
    result = M.list_templates(db, workspace_id=R.W1.id, skip=1, limit=1)
    # Then 1
    assert [t.id for t in result] == [t3.id]


def test_wtmg_lt_05__default_limit_100(db, R):
    """WTMG-LT-05 — the default limit is 100.
    Rules: list_templates R1."""
    e = many_templates(db, R, 101)
    result = M.list_templates(db, workspace_id=R.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert e[0].id not in {t.id for t in result}


def test_wtmg_lt_06__limit_1000_gives_all(db, R):
    """WTMG-LT-06 — limit=1000 gives all 101.
    Rules: list_templates R1."""
    many_templates(db, R, 101)
    result = M.list_templates(db, workspace_id=R.W1.id, limit=1000)
    # Then 1
    assert len(result) == 101


def test_wtmg_lt_07__writes_nothing(db, R):
    """WTMG-LT-07 — writes nothing: a pending row and an unflushed edit stay as they were.
    Rules: list_templates R1."""
    t1 = tpl(db, R, created_at=_at(2))
    t2 = tpl(db, R, created_at=_at(3))
    t2.notes = "Edited"
    p = WorkOrderTemplate(workspace_id=R.W1.id, template_name="Pending", work_order_type_id=R.WT1.id)
    db.add(p)
    result = M.list_templates(db, workspace_id=R.W1.id)
    # Then 1
    assert t1.id in {t.id for t in result}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# delete_template
# --------------------------------------------------------------------------- #

def test_wtmg_dt_01__active_template_deactivated_and_stamped(db, R):
    """WTMG-DT-01 — an active template is deactivated and stamped; lines, approvers and orders untouched.
    Rules: delete_template R2, Returns."""
    t = tpl(db, R, requires_approval=True)
    ln = line(db, R, t, R.I1)
    x = approver(db, R, t, R.U1)
    o = order(db, R, "O", R.M1, D(16), work_order_template_id=t.id)
    before_l, before_x, before_o = snap(db, ln), snap(db, x), snap(db, o)
    result = M.delete_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.is_active is False
    assert row.updated_by == R.U2.id
    # Then 4
    assert unchanged_snap(db, ln) == before_l
    # Then 5
    assert unchanged_snap(db, x) == before_x
    # Then 6
    assert unchanged_snap(db, o) == before_o


def test_wtmg_dt_02__unknown_id_404(db, R):
    """WTMG-DT-02 — an unknown id is 404, nothing changes.
    Rules: delete_template R1."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=MISSING, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, t) == before


def test_wtmg_dt_03__template_of_w2_404(db, R):
    """WTMG-DT-03 — a template of W2 (a later row) is 404 in W1.
    Rules: delete_template R1."""
    tpl(db, R)
    z = tpl_w2(db, R)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=z.id, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, z) == before


def test_wtmg_dt_04__template_of_w0_404(db, R):
    """WTMG-DT-04 — a template of W0 (an earlier row) is 404 in W1.
    Rules: delete_template R1."""
    z = tpl_w0(db, R)
    tpl(db, R)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=z.id, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, z) == before


def test_wtmg_dt_05__inactive_template_no_stamp(db, R):
    """WTMG-DT-05 — an inactive template: no error, no stamp, nothing written.
    Rules: delete_template R3."""
    t = tpl(db, R, is_active=False)
    before = snap(db, t)
    result = M.delete_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    assert unchanged_snap(db, t) == before
    # Then 4
    assert reread(db, WorkOrderTemplate, t.id).updated_by is None


def test_wtmg_dt_06__delete_flushes_never_commits(db, R):
    """WTMG-DT-06 — delete flushes and never commits.
    Rules: delete_template R2, Side effects."""
    t = tpl(db, R)
    tid = t.id
    c = WorkOrderTemplate.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        M.delete_template(db, tpl_id=tid, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.is_active.is_(False)) == 1
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.is_active.is_(False)) == 0


# --------------------------------------------------------------------------- #
# restore_template
# --------------------------------------------------------------------------- #

def test_wtmg_rt_01__inactive_template_restored_and_stamped(db, R):
    """WTMG-RT-01 — an inactive template is restored and stamped.
    Rules: restore_template R2, Returns."""
    t = tpl(db, R, is_active=False)
    result = M.restore_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.is_active is True
    assert row.updated_by == R.U2.id


def test_wtmg_rt_02__unknown_id_404(db, R):
    """WTMG-RT-02 — an unknown id is 404, nothing changes.
    Rules: restore_template R1."""
    t = tpl(db, R, is_active=False)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.restore_template(db, tpl_id=MISSING, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, t) == before


def test_wtmg_rt_03__template_of_w2_404(db, R):
    """WTMG-RT-03 — a template of W2 (a later row) is 404 in W1.
    Rules: restore_template R1."""
    tpl(db, R, is_active=False)
    z = tpl_w2(db, R, is_active=False)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.restore_template(db, tpl_id=z.id, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, z) == before


def test_wtmg_rt_04__template_of_w0_404(db, R):
    """WTMG-RT-04 — a template of W0 (an earlier row) is 404 in W1.
    Rules: restore_template R1."""
    z = tpl_w0(db, R, is_active=False)
    tpl(db, R, is_active=False)
    before = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.restore_template(db, tpl_id=z.id, workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, z) == before


def test_wtmg_rt_05__active_template_stays_active(db, R):
    """WTMG-RT-05 — an already active template is returned and stays active.
    Rules: restore_template R2."""
    t = tpl(db, R)
    result = M.restore_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).is_active is True


@xf("BUG-2340")
def test_wtmg_rt_06__active_template_no_stamp(db, R):
    """WTMG-RT-06 — an already active template gets no stamp.
    Rules: restore_template R2 [BUG-2340]."""
    t = tpl(db, R)
    result = M.restore_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by is None
    assert row.updated_at is None


def test_wtmg_rt_07__deleted_type_and_machine_kept(db, R):
    """WTMG-RT-07 — a type and machine deleted meanwhile are kept on restore.
    Rules: restore_template R3."""
    wd = mk(db, WorkOrderType, workspace_id=R.W1.id, name="Old", **gone(R))
    mg = mk(db, Machine, workspace_id=R.W1.id, factory_id=R.F1.id, name="Old press", **gone_off(R))
    t = tpl(db, R, work_order_type_id=wd.id, default_machine_id=mg.id, is_active=False)
    result = M.restore_template(db, tpl_id=t.id, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.is_active is True
    assert row.work_order_type_id == wd.id
    assert row.default_machine_id == mg.id


def test_wtmg_rt_08__restore_flushes_never_commits(db, R):
    """WTMG-RT-08 — restore flushes and never commits.
    Rules: restore_template R2, Side effects."""
    t = tpl(db, R, is_active=False)
    tid = t.id
    c = WorkOrderTemplate.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.restore_template(db, tpl_id=tid, workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == tid
    # Then 2
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.is_active.is_(True)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrderTemplate, c.id == tid, c.is_active.is_(True)) == 0


# --------------------------------------------------------------------------- #
# add_item
# --------------------------------------------------------------------------- #

def _items_of(tpl_id):
    return WorkOrderTemplateItem.__table__.c.work_order_template_id == tpl_id


def test_wtmg_ai_01__line_stored_with_every_field(db, R):
    """WTMG-AI-01 — a line is stored with the template's id, the workspace and every field sent.
    Rules: add_item R4, Returns."""
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, quantity=Decimal("2.5"), action_type="INSTALL",
                                                 notes="Left side"), workspace_id=R.W1.id)
    # Then 1
    assert isinstance(result, WorkOrderTemplateItem)
    assert result.id is not None
    # Then 2
    assert not db.new
    lid = result.id
    # Then 3
    row = reread(db, WorkOrderTemplateItem, lid)
    assert row.workspace_id == R.W1.id
    assert row.work_order_template_id == t.id
    assert row.item_id == R.I1.id
    # Then 4
    row = reread(db, WorkOrderTemplateItem, lid)
    assert row.quantity == Decimal("2.50")
    assert row.action_type == "INSTALL"
    assert row.notes == "Left side"
    assert row.replaced_item_id is None


def test_wtmg_ai_02__defaults_quantity_1_consume(db, R):
    """WTMG-AI-02 — defaults: quantity 1, action CONSUME.
    Rules: add_item R4."""
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderTemplateItem, result.id)
    assert row.quantity == Decimal("1.00")
    assert row.action_type == "CONSUME"


def test_wtmg_ai_03__unknown_template_404(db, R):
    """WTMG-AI-03 — an unknown template is 404, nothing written.
    Rules: add_item R1."""
    tpl(db, R)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=MISSING, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ai_04__template_of_w2_404(db, R):
    """WTMG-AI-04 — a template of W2 (a later row) is 404 in W1.
    Rules: add_item R1."""
    tpl(db, R)
    z = tpl_w2(db, R)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=z.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ai_05__template_of_w0_404(db, R):
    """WTMG-AI-05 — a template of W0 (an earlier row) is 404 in W1.
    Rules: add_item R1."""
    z = tpl_w0(db, R)
    tpl(db, R)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=z.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Work order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ai_06__inactive_template_accepts_lines(db, R):
    """WTMG-AI-06 — an inactive template accepts lines.
    Rules: add_item R1."""
    t = tpl(db, R, is_active=False)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [ln.item_id for ln in lines(db, t.id)] == [R.I1.id]


def test_wtmg_ai_07__replace_without_item_refused(db, R):
    """WTMG-AI-07 — REPLACE with no replaced item is refused, nothing written.
    Rules: add_item R2, Errors."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, action_type="REPLACE"), workspace_id=R.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


def test_wtmg_ai_08__replace_with_item_stored(db, R):
    """WTMG-AI-08 — REPLACE with a replaced item is stored.
    Rules: add_item R2, R4."""
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, action_type="REPLACE", replaced_item_id=R.I2.id),
                        workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderTemplateItem, result.id)
    assert row.action_type == "REPLACE"
    assert row.replaced_item_id == R.I2.id


@xf("BUG-2337")
@pytest.mark.parametrize("action", [
    pytest.param("CONSUME", id="WTMG-AI-09"),
    pytest.param("BORROW", id="WTMG-AI-10"),
])
def test_wtmg_ai_09_10__replaced_item_on_other_action_refused(db, R, action):
    """WTMG-AI-09 / AI-10 — a replaced item on a CONSUME or BORROW line is refused.
    Rules: add_item R2a [BUG-2337]."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, action_type=action, replaced_item_id=R.I2.id),
                   workspace_id=R.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "replaced_item_id only applies to Replace"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


@xf("BUG-2338")
def test_wtmg_ai_11__item_already_on_template_409(db, R):
    """WTMG-AI-11 — an item already on the template is refused with 409.
    Rules: add_item R2b [BUG-2338]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, quantity=Decimal(2)), workspace_id=R.W1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Oil filter is already on this template"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert [x.id for x in lines(db, t.id)] == [ln.id]


def test_wtmg_ai_12__item_on_other_template_does_not_block(db, R):
    """WTMG-AI-12 — an item on another template does not block.
    Rules: add_item R2b."""
    s = tpl(db, R, template_name="Belt check")
    line(db, R, s, R.I1)
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [ln.item_id for ln in lines(db, t.id)] == [R.I1.id]


@xf("BUG-1015")
def test_wtmg_ai_13__item_of_w2_refused(db, R):
    """WTMG-AI-13 — an item of W2 is refused as not found.
    Rules: add_item R3 [BUG-1015]."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I9.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


@xf("BUG-1015")
def test_wtmg_ai_14__item_of_w0_refused(db, R):
    """WTMG-AI-14 — an item of W0 is refused as not found.
    Rules: add_item R3 [BUG-1015]."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I0.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


@xf("BUG-1015")
def test_wtmg_ai_15__unknown_item_refused(db, R):
    """WTMG-AI-15 — an unknown item is refused as not found.
    Rules: add_item R3 [BUG-1015]."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=MISSING), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


@xf("BUG-1015")
def test_wtmg_ai_16__replaced_item_of_w2_refused(db, R):
    """WTMG-AI-16 — a replaced item of W2 is refused as not found.
    Rules: add_item R3 [BUG-1015]."""
    t = tpl(db, R)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, action_type="REPLACE", replaced_item_id=R.I9.id),
                   workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert n_rows(db, WorkOrderTemplateItem, _items_of(t.id)) == 0


def test_wtmg_ai_17__adding_line_writes_no_stamp(db, R):
    """WTMG-AI-17 — adding a line writes no stamp on the template.
    Rules: add_item R4."""
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.updated_by is None
    assert row.updated_at is None


@xf("BUG-2350")
@pytest.mark.parametrize("qty", [
    pytest.param("0.005", id="WTMG-AI-18"),
    pytest.param("0.004", id="WTMG-AI-19"),
    pytest.param("0.125", id="WTMG-AI-20"),
    pytest.param("2.345", id="WTMG-AI-21"),
    pytest.param("-1.005", id="WTMG-AI-23"),
    pytest.param("10000000000000", id="WTMG-AI-26"),
])
def test_wtmg_ai_18_23_26__quantity_out_of_range_refused_by_schema(db, R, qty):
    """WTMG-AI-18 … AI-21, AI-23, AI-26 — a quantity with three decimals or 14 integer digits is refused by the schema.
    Rules: add_item R5 [BUG-2350]; HR-15."""
    tpl(db, R)
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        IC(item_id=R.I1.id, quantity=Decimal(qty))
    # Then 2
    assert counts(db) == before


@pytest.mark.parametrize(("qty", "stored"), [
    pytest.param("0", "0.00", id="WTMG-AI-22"),
    pytest.param("9999999999999.99", "9999999999999.99", id="WTMG-AI-24"),
    pytest.param("0.01", "0.01", id="WTMG-AI-27"),
])
def test_wtmg_ai_22_24_27__quantity_in_range_stored_exactly(db, R, qty, stored):
    """WTMG-AI-22, AI-24, AI-27 — quantity 0, the largest Numeric(15, 2) value and the smallest step are stored exactly.
    Rules: add_item R4, R5; HR-15."""
    t = tpl(db, R)
    result = M.add_item(db, tpl_id=t.id, data=IC(item_id=R.I1.id, quantity=Decimal(qty)), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderTemplateItem, result.id).quantity == Decimal(stored)


def test_wtmg_ai_25__add_item_flushes_never_commits(db, R):
    """WTMG-AI-25 — add_item flushes and never commits.
    Rules: add_item Side effects."""
    t = tpl(db, R)
    tid = t.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.add_item(db, tpl_id=tid, data=IC(item_id=R.I1.id), workspace_id=R.W1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert n_rows(db, WorkOrderTemplateItem, _items_of(tid)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrderTemplateItem, _items_of(tid)) == 0


# --------------------------------------------------------------------------- #
# update_item
# --------------------------------------------------------------------------- #

def test_wtmg_ui_01__sent_fields_changed_rest_kept(db, R):
    """WTMG-UI-01 — sent fields are changed, the rest kept.
    Rules: update_item R3, Returns."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    result = M.update_item(db, item_id=ln.id, data=IU(quantity=Decimal(3), notes="Torque 40"), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert not db.dirty
    # Then 3
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.quantity == Decimal("3.00")
    assert row.notes == "Torque 40"
    # Then 4
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.item_id == R.I1.id
    assert row.action_type == "CONSUME"
    assert row.work_order_template_id == t.id


def test_wtmg_ui_02__unknown_line_404(db, R):
    """WTMG-UI-02 — an unknown line is 404.
    Rules: update_item R1."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=MISSING, data=IU(notes="x"), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


def test_wtmg_ui_03__line_of_w2_404(db, R):
    """WTMG-UI-03 — a line of W2 (a later row) is 404 in W1.
    Rules: update_item R1."""
    t = tpl(db, R)
    line(db, R, t, R.I1)
    z = tpl_w2(db, R)
    k = line(db, R, z, R.I9, workspace_id=R.W2.id)
    before = snap(db, k)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=k.id, data=IU(notes="x"), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, k) == before


def test_wtmg_ui_04__line_of_w0_404(db, R):
    """WTMG-UI-04 — a line of W0 (an earlier row) is 404 in W1.
    Rules: update_item R1."""
    z = tpl_w0(db, R)
    k = line(db, R, z, R.I0, workspace_id=R.W0.id)
    t = tpl(db, R)
    line(db, R, t, R.I1)
    before = snap(db, k)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=k.id, data=IU(notes="x"), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, k) == before


def test_wtmg_ui_05__template_id_is_not_a_line_id(db, R):
    """WTMG-UI-05 — item_id names a line, not a template: a template id with no such line is 404.
    Rules: update_item R1."""
    tpl(db, R, id=770001)
    s = tpl(db, R, id=770002, template_name="Belt check")
    ln = line(db, R, s, R.I1, id=770002)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=770001, data=IU(notes="x"), workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


@xf("BUG-2336")
def test_wtmg_ui_06__switch_to_replace_without_item_refused(db, R):
    """WTMG-UI-06 — switching to REPLACE with no replaced item is refused.
    Rules: update_item R2 [BUG-2336]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=ln.id, data=IU(action_type="REPLACE"), workspace_id=R.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


@xf("BUG-2336")
def test_wtmg_ui_07__clearing_replaced_item_of_replace_line_refused(db, R):
    """WTMG-UI-07 — clearing the replaced item of a REPLACE line is refused.
    Rules: update_item R2, R3 (a REPLACE line keeps its item, spec G9) [BUG-2336]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, action_type="REPLACE", replaced_item_id=R.I2.id)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=ln.id, data=IU(replaced_item_id=None), workspace_id=R.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


def test_wtmg_ui_08__switch_to_replace_with_item_stored(db, R):
    """WTMG-UI-08 — switching to REPLACE with a replaced item is stored.
    Rules: update_item R2."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    result = M.update_item(db, item_id=ln.id, data=IU(action_type="REPLACE", replaced_item_id=R.I2.id),
                           workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.action_type == "REPLACE"
    assert row.replaced_item_id == R.I2.id


def test_wtmg_ui_09__replace_line_keeps_item_on_quantity_change(db, R):
    """WTMG-UI-09 — a REPLACE line keeps its stored replaced item on a quantity change.
    Rules: update_item R2."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, action_type="REPLACE", replaced_item_id=R.I2.id)
    result = M.update_item(db, item_id=ln.id, data=IU(quantity=Decimal(2)), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.quantity == Decimal("2.00")
    assert row.action_type == "REPLACE"
    assert row.replaced_item_id == R.I2.id


@xf("BUG-2337")
def test_wtmg_ui_10__switch_away_from_replace_clears_item(db, R):
    """WTMG-UI-10 — switching away from REPLACE clears the replaced item.
    Rules: update_item R2a [BUG-2337]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, action_type="REPLACE", replaced_item_id=R.I2.id)
    result = M.update_item(db, item_id=ln.id, data=IU(action_type="INSTALL"), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderTemplateItem, ln.id).action_type == "INSTALL"
    # Then 3
    assert reread(db, WorkOrderTemplateItem, ln.id).replaced_item_id is None


def test_wtmg_ui_11__switch_away_from_replace_stores_action(db, R):
    """WTMG-UI-11 — switching away from REPLACE: the new action is stored.
    Rules: update_item R3."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, action_type="REPLACE", replaced_item_id=R.I2.id)
    result = M.update_item(db, item_id=ln.id, data=IU(action_type="INSTALL"), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.action_type == "INSTALL"
    assert row.item_id == R.I1.id


@xf("BUG-2337")
def test_wtmg_ui_12__replaced_item_on_consume_line_refused(db, R):
    """WTMG-UI-12 — a replaced item sent on a CONSUME line is refused.
    Rules: update_item R2a [BUG-2337]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=ln.id, data=IU(replaced_item_id=R.I2.id), workspace_id=R.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "replaced_item_id only applies to Replace"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


@xf("BUG-2339")
def test_wtmg_ui_13__null_clears_notes(db, R):
    """WTMG-UI-13 — an explicit null clears the notes.
    Rules: update_item R3 [BUG-2339]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, notes="Torque 40")
    result = M.update_item(db, item_id=ln.id, data=IU(notes=None), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderTemplateItem, ln.id).notes is None


@xf("BUG-2339")
@pytest.mark.parametrize("field", [
    pytest.param("quantity", id="WTMG-UI-14"),
    pytest.param("action_type", id="WTMG-UI-15"),
])
def test_wtmg_ui_14_15__null_for_required_line_field_rejected(db, R, field):
    """WTMG-UI-14 / UI-15 — null for quantity or action_type is rejected by the schema.
    Rules: update_item R3 [BUG-2339]."""
    tpl(db, R)
    # Then 1
    with pytest.raises(ValidationError):
        IU(**{field: None})


@xf("BUG-1015")
def test_wtmg_ui_16__replaced_item_of_w2_refused(db, R):
    """WTMG-UI-16 — a replaced item of W2 is refused as not found.
    Rules: update_item R4 [BUG-1015]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=ln.id, data=IU(action_type="REPLACE", replaced_item_id=R.I9.id),
                      workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {R.I9.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


@xf("BUG-1015")
def test_wtmg_ui_17__unknown_replaced_item_refused(db, R):
    """WTMG-UI-17 — an unknown replaced item is refused as not found.
    Rules: update_item R4 [BUG-1015]."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=ln.id, data=IU(action_type="REPLACE", replaced_item_id=MISSING),
                      workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert unchanged_snap(db, ln) == before


def test_wtmg_ui_18__line_of_inactive_template_updated(db, R):
    """WTMG-UI-18 — a line of an inactive template can be updated.
    Rules: update_item R5."""
    t = tpl(db, R, is_active=False)
    ln = line(db, R, t, R.I1)
    result = M.update_item(db, item_id=ln.id, data=IU(notes="x"), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderTemplateItem, ln.id).notes == "x"


@xf("BUG-2350")
@pytest.mark.parametrize("qty", [
    pytest.param("2.345", id="WTMG-UI-19"),
    pytest.param("-1.005", id="WTMG-UI-21"),
    pytest.param("10000000000000", id="WTMG-UI-23"),
])
def test_wtmg_ui_19_21_23__sent_quantity_out_of_range_refused_by_schema(db, R, qty):
    """WTMG-UI-19, UI-21, UI-23 — a sent quantity with three decimals or 14 integer digits is refused by the schema.
    Rules: update_item R3a [BUG-2350]; HR-15."""
    t = tpl(db, R)
    line(db, R, t, R.I1, quantity=Decimal(1))
    before = counts(db)
    # Then 1
    with pytest.raises(ValidationError):
        IU(quantity=Decimal(qty))
    # Then 2
    assert counts(db) == before


def test_wtmg_ui_20__quantity_zero_replaces_old(db, R):
    """WTMG-UI-20 — quantity 0 is stored as 0.00 (zero replaces 3.00).
    Rules: update_item R3; HR-15."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, quantity=Decimal(3))
    result = M.update_item(db, item_id=ln.id, data=IU(quantity=Decimal(0)), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderTemplateItem, ln.id).quantity == Decimal("0.00")


def test_wtmg_ui_22__update_item_flushes_never_commits(db, R):
    """WTMG-UI-22 — update_item flushes and never commits.
    Rules: update_item Side effects."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    lid = ln.id
    c = WorkOrderTemplateItem.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.update_item(db, item_id=lid, data=IU(notes="Rolled"), workspace_id=R.W1.id)
    # Then 1
    assert result.id == lid
    # Then 2
    assert n_rows(db, WorkOrderTemplateItem, c.id == lid, c.notes == "Rolled") == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrderTemplateItem, c.id == lid, c.notes == "Rolled") == 0


@xf("BUG-2339")
def test_wtmg_ui_24__null_clears_replaced_item_of_non_replace_line(db, R):
    """WTMG-UI-24 — an explicit null clears the replaced item of a line that is not REPLACE.
    Rules: update_item R3 [BUG-2339] (spec G9)."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, action_type="INSTALL", replaced_item_id=R.I2.id)
    result = M.update_item(db, item_id=ln.id, data=IU(replaced_item_id=None), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderTemplateItem, ln.id)
    assert row.replaced_item_id is None
    assert row.action_type == "INSTALL"


@pytest.mark.parametrize("qty", [
    pytest.param("9999999999999.99", id="WTMG-UI-25"),
    pytest.param("0.01", id="WTMG-UI-26"),
])
def test_wtmg_ui_25_26__quantity_at_bounds_stored_exactly(db, R, qty):
    """WTMG-UI-25 / UI-26 — the largest quantity (9999999999999.99) and the smallest step (0.01) are stored exactly.
    Rules: update_item R3a (BUG-2350 bounds, accepted)."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, quantity=Decimal(3))
    result = M.update_item(db, item_id=ln.id, data=IU(quantity=Decimal(qty)), workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderTemplateItem, ln.id).quantity == Decimal(qty)


# --------------------------------------------------------------------------- #
# remove_item
# --------------------------------------------------------------------------- #

def test_wtmg_ri_01__line_hard_deleted_others_stay(db, R):
    """WTMG-RI-01 — the line is hard-deleted, the others stay, its values stay readable.
    Rules: remove_item R2, Returns."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1, quantity=Decimal(2))
    k = line(db, R, t, R.I2)
    lid, before_k = ln.id, snap(db, k)
    result = M.remove_item(db, item_id=lid, workspace_id=R.W1.id)
    # Then 1
    assert result.item_id == R.I1.id
    assert result.quantity == Decimal("2.00")
    # Then 2
    assert not db.deleted
    # Then 3
    assert n_rows(db, WorkOrderTemplateItem, WorkOrderTemplateItem.__table__.c.id == lid) == 0
    # Then 4
    assert unchanged_snap(db, k) == before_k


def test_wtmg_ri_02__unknown_line_404(db, R):
    """WTMG-RI-02 — an unknown line is 404.
    Rules: remove_item R1."""
    t = tpl(db, R)
    line(db, R, t, R.I1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=MISSING, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ri_03__line_of_w2_404(db, R):
    """WTMG-RI-03 — a line of W2 (a later row) is 404 in W1.
    Rules: remove_item R1."""
    t = tpl(db, R)
    line(db, R, t, R.I1)
    z = tpl_w2(db, R)
    k = line(db, R, z, R.I9, workspace_id=R.W2.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=k.id, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ri_04__line_of_w0_404(db, R):
    """WTMG-RI-04 — a line of W0 (an earlier row) is 404 in W1.
    Rules: remove_item R1."""
    z = tpl_w0(db, R)
    k = line(db, R, z, R.I0, workspace_id=R.W0.id)
    t = tpl(db, R)
    line(db, R, t, R.I1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=k.id, workspace_id=R.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted
    # Then 6
    assert counts(db) == before


def test_wtmg_ri_05__line_id_not_template_id(db, R):
    """WTMG-RI-05 — item_id names a line: the line with that id goes, the template with the same id stays.
    Rules: remove_item R2."""
    t = tpl(db, R, id=770001)
    s = tpl(db, R, id=770002, template_name="Belt check")
    ln = line(db, R, t, R.I1, id=770002)
    line(db, R, s, R.I2, id=770001)
    before_l, before_t = snap(db, ln), snap(db, t)
    result = M.remove_item(db, item_id=770001, workspace_id=R.W1.id)
    # Then 1
    assert result.item_id == R.I2.id
    # Then 2
    assert n_rows(db, WorkOrderTemplateItem, WorkOrderTemplateItem.__table__.c.id == 770001) == 0
    # Then 3
    assert unchanged_snap(db, ln) == before_l
    # Then 4
    assert unchanged_snap(db, t) == before_t


def test_wtmg_ri_06__remove_flushes_never_commits(db, R):
    """WTMG-RI-06 — remove_item flushes and never commits.
    Rules: remove_item R2, Side effects."""
    t = tpl(db, R)
    ln = line(db, R, t, R.I1)
    lid = ln.id
    c = WorkOrderTemplateItem.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        M.remove_item(db, item_id=lid, workspace_id=R.W1.id)
    # Then 1
    assert n_rows(db, WorkOrderTemplateItem, c.id == lid) == 0
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert n_rows(db, WorkOrderTemplateItem, c.id == lid) == 1


# [claude] WTMG-RI-07
def test_wtmg_ri_07__order_keeps_copied_line(db, R):
    """WTMG-RI-07 — a work order made earlier keeps its copied line when the template line is removed.
    Rules: remove_item R2 (spec G12).
    The card's columns plus workspace_id (W1), the one other NOT NULL column of
    work_order_items without a default; the rest have defaults."""
    t = tpl(db, R, uses_inventory=True)
    ln = line(db, R, t, R.I1, quantity=Decimal(2))
    o = order(db, R, "O", R.M1, D(16), work_order_template_id=t.id)
    wi = mk(db, WorkOrderItem, workspace_id=R.W1.id, work_order_id=o.id, item_id=R.I1.id, quantity=Decimal(2),
            action_type="CONSUME", replaced_item_id=None)
    before_wi = snap(db, wi)
    result = M.remove_item(db, item_id=ln.id, workspace_id=R.W1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert lines(db, t.id) == []
    # Then 3
    assert unchanged_snap(db, wi) == before_wi
    # Then 4
    row = reread(db, WorkOrderItem, wi.id)
    assert row.item_id == R.I1.id
    assert row.quantity == Decimal("2.00")
    assert row.action_type == "CONSUME"


# --------------------------------------------------------------------------- #
# get_items
# --------------------------------------------------------------------------- #

def test_wtmg_gi_01__all_lines_in_id_order(db, R):
    """WTMG-GI-01 — all lines of the template in id order.
    Rules: get_items R1."""
    s = tpl(db, R, template_name="Belt check")
    t = tpl(db, R)
    a = line(db, R, t, R.I2)
    line(db, R, s, R.I1)
    b = line(db, R, t, R.I1)
    result = M.get_items(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [a.id, b.id]


def test_wtmg_gi_02__unknown_template_empty(db, R):
    """WTMG-GI-02 — an unknown template gives an empty list.
    Rules: get_items R1."""
    t = tpl(db, R)
    line(db, R, t, R.I1)
    result = M.get_items(db, tpl_id=MISSING, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_gi_03__template_of_w2_empty(db, R):
    """WTMG-GI-03 — a template of W2 asked for in W1 gives an empty list.
    Rules: get_items R1."""
    tpl(db, R)
    z = tpl_w2(db, R)
    line(db, R, z, R.I9, workspace_id=R.W2.id)
    result = M.get_items(db, tpl_id=z.id, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_gi_04__template_of_w0_empty(db, R):
    """WTMG-GI-04 — a template of W0 asked for in W1 gives an empty list.
    Rules: get_items R1."""
    z = tpl_w0(db, R)
    line(db, R, z, R.I0, workspace_id=R.W0.id)
    tpl(db, R)
    result = M.get_items(db, tpl_id=z.id, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_gi_05__lines_of_inactive_template(db, R):
    """WTMG-GI-05 — the lines of an inactive template are returned.
    Rules: get_items R1."""
    t = tpl(db, R, is_active=False)
    a = line(db, R, t, R.I1)
    result = M.get_items(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [a.id]


def test_wtmg_gi_06__writes_nothing(db, R):
    """WTMG-GI-06 — writes nothing: a pending row and an unflushed edit stay.
    Rules: get_items R1."""
    t = tpl(db, R)
    a = line(db, R, t, R.I1)
    a.notes = "Edited"
    p = WorkOrderTemplate(workspace_id=R.W1.id, template_name="Pending", work_order_type_id=R.WT1.id)
    db.add(p)
    result = M.get_items(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# get_approvers
# --------------------------------------------------------------------------- #

def test_wtmg_ga_01__template_approver_rows(db, R):
    """WTMG-GA-01 — the template's approver rows.
    Rules: get_approvers R1."""
    s = tpl(db, R, template_name="Belt check")
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U2)
    approver(db, R, s, R.U4)
    approver(db, R, t, R.U1)
    result = M.get_approvers(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert {a.user_id for a in result} == {R.U1.id, R.U2.id}


def test_wtmg_ga_02__unknown_template_empty(db, R):
    """WTMG-GA-02 — an unknown template gives an empty list.
    Rules: get_approvers R1."""
    t = tpl(db, R)
    approver(db, R, t, R.U1)
    result = M.get_approvers(db, tpl_id=MISSING, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_ga_03__template_of_w2_empty(db, R):
    """WTMG-GA-03 — a template of W2 asked for in W1 gives an empty list.
    Rules: get_approvers R1."""
    tpl(db, R)
    z = tpl_w2(db, R)
    approver(db, R, z, R.U3, workspace_id=R.W2.id)
    result = M.get_approvers(db, tpl_id=z.id, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_ga_04__template_of_w0_empty(db, R):
    """WTMG-GA-04 — a template of W0 asked for in W1 gives an empty list.
    Rules: get_approvers R1."""
    z = tpl_w0(db, R)
    approver(db, R, z, R.U5, workspace_id=R.W0.id)
    tpl(db, R)
    result = M.get_approvers(db, tpl_id=z.id, workspace_id=R.W1.id)
    # Then 1
    assert result == []


def test_wtmg_ga_05__writes_nothing(db, R):
    """WTMG-GA-05 — writes nothing: a pending row and an unflushed edit stay.
    Rules: get_approvers R1."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    t.notes = "Edited"
    p = WorkOrderTemplate(workspace_id=R.W1.id, template_name="Pending", work_order_type_id=R.WT1.id)
    db.add(p)
    result = M.get_approvers(db, tpl_id=t.id, workspace_id=R.W1.id)
    # Then 1
    assert {a.user_id for a in result} == {R.U1.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# generate_drafts_for_anchored_range
# --------------------------------------------------------------------------- #

def test_wtmg_ar_01__daily_one_draft_per_date(db, R):
    """WTMG-AR-01 — daily: one draft per date up to the end, in date order; next date is the day after the end.
    Rules: anchored R2, R3, Returns."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(4))
    result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                  user_id=R.U1.id)
    # Then 1
    assert [o.planned_date for o in result] == [D(2), D(3), D(4)]
    # Then 2
    assert {o.machine_id for o in result} == {R.M1.id}
    # Then 3
    assert t.next_generation_date == D(5)
    # Then 4
    assert not db.new
    first_id = result[0].id
    # Then 5
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(5)
    # Then 6
    assert drafts(db, t.id) == [(D(2), R.M1.id), (D(3), R.M1.id), (D(4), R.M1.id)]
    # Then 7
    first = reread(db, WorkOrder, first_id)
    assert first.status == "DRAFT"
    assert first.work_order_template_id == t.id
    assert first.work_order_type_id == R.WT1.id
    assert first.workspace_id == R.W1.id


@pytest.mark.parametrize(("cadence", "start", "end", "dates", "after"), [
    pytest.param(WEEKLY, D(2), D(23), [D(2), D(9), D(16), D(23)], D(30), id="WTMG-AR-02"),
    pytest.param(WEEKLY, D(2), D(22), [D(2), D(9), D(16)], D(23), id="WTMG-AR-03"),
    pytest.param({"is_recurring": True, "recurrence_type": "weekly"}, D(4), D(18), [D(4), D(11), D(18)], D(25),
                 id="WTMG-AR-04"),
    pytest.param(monthly(31), date(2026, 1, 31), date(2026, 4, 30),
                 [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)], date(2026, 5, 31),
                 id="WTMG-AR-05"),
    pytest.param(monthly(29), date(2028, 1, 29), date(2028, 3, 29),
                 [date(2028, 1, 29), date(2028, 2, 29), date(2028, 3, 29)], date(2028, 4, 29), id="WTMG-AR-06"),
    pytest.param(monthly(31), date(2028, 1, 31), date(2028, 2, 29),
                 [date(2028, 1, 31), date(2028, 2, 29)], date(2028, 3, 31), id="WTMG-AR-07"),
    pytest.param(DAILY, date(2026, 12, 30), date(2027, 1, 1),
                 [date(2026, 12, 30), date(2026, 12, 31), date(2027, 1, 1)], date(2027, 1, 2), id="WTMG-AR-08"),
    pytest.param(DAILY, D(4), D(4), [D(4)], D(5), id="WTMG-AR-09"),
])
def test_wtmg_ar_02_09__cadence_dates_up_to_end(db, R, cadence, start, end, dates, after):
    """WTMG-AR-02 … AR-09 — every cadence date from the next date up to the end, then the first date after it.
    Rules: anchored R2, R3."""
    t = tpl(db, R, **cadence, next_generation_date=start, recurrence_end_date=end)
    result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                  user_id=R.U1.id)
    # Then 1
    assert [o.planned_date for o in result] == dates
    # Then 2
    assert {o.machine_id for o in result} == {R.M1.id}
    # Then 3
    assert t.next_generation_date == after
    # Then 4
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == after
    # Then 5
    assert drafts(db, t.id) == [(d, R.M1.id) for d in dates]


@pytest.mark.parametrize("given", [
    pytest.param({"recurrence_type": "daily", "next_generation_date": D(2), "recurrence_end_date": D(4)},
                 id="WTMG-AR-10"),
    pytest.param({**DAILY, "next_generation_date": D(2)}, id="WTMG-AR-11"),
    pytest.param({**DAILY, "recurrence_end_date": D(4)}, id="WTMG-AR-12"),
    pytest.param({**DAILY, "next_generation_date": D(5), "recurrence_end_date": D(4)}, id="WTMG-AR-13"),
])
def test_wtmg_ar_10_13__nothing_to_generate(db, R, given):
    """WTMG-AR-10 … AR-13 — not recurring, no end date, never anchored, or next date after the end: nothing, T unchanged.
    Rules: anchored R1, R2."""
    t = tpl(db, R, **given)
    before = snap(db, t)
    result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                  user_id=R.U1.id)
    # Then 1
    assert result == []
    # Then 2
    assert not db.new
    # Then 3
    assert unchanged_snap(db, t) == before
    # Then 4
    assert drafts(db, t.id) == []


@pytest.mark.parametrize(("over", "dates"), [
    pytest.param({}, [D(2), D(4)], id="WTMG-AR-14"),
    pytest.param({"status": "COMPLETED"}, [D(2), D(4)], id="WTMG-AR-15"),
    pytest.param({"status": "VOIDED"}, [D(2), D(3), D(4)], id="WTMG-AR-16"),
    pytest.param("deleted", [D(2), D(3), D(4)], id="WTMG-AR-17"),
    pytest.param("other_type", [D(2), D(3), D(4)], id="WTMG-AR-18"),
    pytest.param("other_machine", [D(2), D(3), D(4)], id="WTMG-AR-19"),
])
def test_wtmg_ar_14_19__open_order_blocks_its_date_only(db, R, over, dates):
    """WTMG-AR-14 … AR-19 — an open order (any source, also COMPLETED) on the machine, day and type blocks that date;
    a VOIDED or soft-deleted order, another type or another machine does not.
    Rules: anchored R2; Facts (open order)."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(4))
    if over == "deleted":
        o = order(db, R, "O", R.M1, D(3), is_deleted=True, is_active=False, deleted_at=T0, deleted_by=R.U1.id)
    elif over == "other_type":
        o = order(db, R, "O", R.M1, D(3), work_order_type_id=R.WT2.id)
    elif over == "other_machine":
        o = order(db, R, "O", R.M2, D(3))
    else:
        o = order(db, R, "O", R.M1, D(3), **over)
    before_o = snap(db, o)
    result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                  user_id=R.U1.id)
    # Then 1
    assert [x.planned_date for x in result] == dates
    # Then 2
    assert {x.machine_id for x in result} == {R.M1.id}
    # Then 3
    assert t.next_generation_date == D(5)
    # Then 4
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(5)
    # Then 5
    assert drafts(db, t.id) == [(d, R.M1.id) for d in dates]
    # Then 6
    assert unchanged_snap(db, o) == before_o


def test_wtmg_ar_20__inactive_template_refused_on_first_draft(db, R):
    """WTMG-AR-20 — an inactive template is refused on the first draft, nothing made.
    Rules: anchored R4 (the date stays, spec G11)."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(4), is_active=False)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                             user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Template is inactive"
    # Then 3
    assert t.next_generation_date == D(2)
    # Then 4
    assert drafts(db, t.id) == []


def test_wtmg_ar_21__machine_of_other_workspace_404(db, R):
    """WTMG-AR-21 — a machine of another workspace: the 404 reaches the caller, nothing made.
    Rules: anchored R5 (the date stays at the failing date)."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(4))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M9.id, workspace_id=R.W1.id,
                                             user_id=R.U1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {R.M9.id} not found"
    # Then 3
    assert t.next_generation_date == D(2)
    # Then 4
    assert drafts(db, t.id) == []


@xf("BUG-2343")
def test_wtmg_ar_22__template_row_locked(db, R):
    """WTMG-AR-22 — the template row is locked before the dates are read.
    Rules: anchored R6 [BUG-2343]."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(2))
    with record_sql(db) as log:
        result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                      user_id=R.U1.id)
    # Then 1
    assert [o.planned_date for o in result] == [D(2)]
    # Then 2
    assert len(locks_of(log)) >= 1


def test_wtmg_ar_23__span_not_limited(db, R):
    """WTMG-AR-23 — the span is not limited: 184 daily dates give 184 drafts.
    Rules: anchored R7."""
    t = tpl(db, R, **DAILY, next_generation_date=date(2026, 1, 1), recurrence_end_date=date(2026, 7, 3))
    result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                  user_id=R.U1.id)
    # Then 1
    assert len(result) == 184
    # Then 2
    assert t.next_generation_date == date(2026, 7, 4)
    # Then 3
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == date(2026, 7, 4)
    # Then 4
    assert len(drafts(db, t.id)) == 184


def test_wtmg_ar_24__anchored_flushes_never_commits(db, R):
    """WTMG-AR-24 — anchored generation flushes and never commits.
    Rules: anchored R3, Side effects."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(3))
    tid = t.id
    c = WorkOrder.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                                      user_id=R.U1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert n_rows(db, WorkOrder, c.work_order_template_id == tid) == 2
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrder, c.work_order_template_id == tid) == 0


# [claude] WTMG-AR-25
def test_wtmg_ar_25__later_failure_keeps_earlier_drafts(db, R):
    """WTMG-AR-25 — a failure on a later date keeps the drafts already made; the date stays at the failing date.
    Rules: anchored R5 (spec G10).
    The patch (spec Notes, G6): wom.create_work_order_from_template calls the real
    method on the first call and raises HTTPException(400, "boom") on the second."""
    t = tpl(db, R, **DAILY, next_generation_date=D(2), recurrence_end_date=D(4))
    real = wom.create_work_order_from_template
    calls = []

    def f(*a, **k):
        calls.append((a, k))
        if len(calls) == 1:
            return real(*a, **k)
        raise HTTPException(status_code=400, detail="boom")

    with patch.object(wom, "create_work_order_from_template", side_effect=f), \
            pytest.raises(HTTPException) as exc:
        M.generate_drafts_for_anchored_range(db, template=t, machine_id=R.M1.id, workspace_id=R.W1.id,
                                             user_id=R.U1.id)
    # Then 1
    assert exc.value.detail == "boom"
    # Then 2
    assert len(calls) == 2
    # Then 3
    assert t.next_generation_date == D(3)
    # Then 4
    db.flush()
    assert drafts(db, t.id) == [(D(2), R.M1.id)]


# --------------------------------------------------------------------------- #
# generate_drafts
# --------------------------------------------------------------------------- #

def test_wtmg_gd_01__due_template_one_draft_moves_one_week(db, R):
    """WTMG-GD-01 — a template due on the day gets one draft on its machine and moves one week.
    Rules: generate_drafts R1, R6, R7, R9, Returns."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 3
    assert not db.new
    first_id = result[0].id
    # Then 4
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)
    # Then 5
    first = reread(db, WorkOrder, first_id)
    assert first.status == "DRAFT"
    assert first.work_order_template_id == t.id
    assert first.work_order_type_id == R.WT1.id
    assert first.workspace_id == R.W1.id


@pytest.mark.parametrize("given", [
    pytest.param({**WEEKLY, "next_generation_date": D(17)}, id="WTMG-GD-02"),
    pytest.param({**WEEKLY}, id="WTMG-GD-03"),
    pytest.param({**WEEKLY, "next_generation_date": D(16), "recurrence_end_date": D(15)}, id="WTMG-GD-05"),
    pytest.param({**WEEKLY, "next_generation_date": D(16), "is_active": False}, id="WTMG-GD-06"),
    pytest.param({"next_generation_date": D(16)}, id="WTMG-GD-07"),
])
def test_wtmg_gd_02_07__template_not_taken_unscoped(db, R, given):
    """WTMG-GD-02, GD-03, GD-05, GD-06, GD-07 — due tomorrow, never anchored, ended the day before, inactive, or
    non-recurring: an unscoped run gives nothing and leaves T unchanged.
    Rules: generate_drafts R1, R2, R8; delete_template R4."""
    t = tpl(db, R, default_machine_id=R.M1.id, **given)
    before = snap(db, t)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert unchanged_snap(db, t) == before
    # Then 3
    assert drafts(db, t.id) == []


def test_wtmg_gd_04__end_equal_to_day_still_drafts(db, R):
    """WTMG-GD-04 — an end date equal to the day still gives a draft, and the date moves past the end.
    Rules: generate_drafts R1, R9."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16), recurrence_end_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)


def test_wtmg_gd_08__other_workspaces_get_nothing(db, R):
    """WTMG-GD-08 — due templates of W0 and W2 get nothing in a run for W1.
    Rules: generate_drafts R1."""
    z0 = tpl_w0(db, R, **WEEKLY, default_machine_id=R.M0.id, next_generation_date=D(16))
    tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    z9 = tpl_w2(db, R, **WEEKLY, default_machine_id=R.M9.id, next_generation_date=D(16))
    before0, before9 = snap(db, z0), snap(db, z9)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 2
    assert unchanged_snap(db, z0) == before0
    # Then 3
    assert unchanged_snap(db, z9) == before9
    # Then 4
    assert drafts(db, z0.id) == []
    # Then 5
    assert drafts(db, z9.id) == []


def test_wtmg_gd_09__no_templates_empty_list(db, R):
    """WTMG-GD-09 — a workspace with no templates gives an empty list.
    Rules: generate_drafts R1, Returns."""
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert n_rows(db, WorkOrder) == 0


@pytest.mark.parametrize(("cadence", "day", "after"), [
    pytest.param(DAILY, D(16), D(17), id="WTMG-GD-10"),
    pytest.param({"is_recurring": True, "recurrence_type": "weekly"}, D(18), D(25), id="WTMG-GD-11"),
    pytest.param({"is_recurring": True, "recurrence_type": "weekly", "recurrence_day": 4}, D(16), D(20),
                 id="WTMG-GD-12"),
    pytest.param(monthly(31), date(2026, 1, 31), date(2026, 2, 28), id="WTMG-GD-13"),
    pytest.param(monthly(31), date(2026, 3, 31), date(2026, 4, 30), id="WTMG-GD-14"),
    pytest.param(monthly(15), date(2026, 12, 15), date(2027, 1, 15), id="WTMG-GD-15"),
    pytest.param(DAILY, date(2026, 12, 31), date(2027, 1, 1), id="WTMG-GD-16"),
    pytest.param(monthly(29), date(2028, 1, 29), date(2028, 2, 29), id="WTMG-GD-17"),
    pytest.param(monthly(31), date(2028, 1, 31), date(2028, 2, 29), id="WTMG-GD-18"),
    pytest.param(monthly(29), date(2027, 1, 29), date(2027, 2, 28), id="WTMG-GD-19"),
])
def test_wtmg_gd_10_19__next_date_after_one_step(db, R, cadence, day, after):
    """WTMG-GD-10 … GD-19 — one draft on the due day and the next date one cadence step later.
    Rules: generate_drafts R7, R9; recurrence advance_next_generation_date."""
    t = tpl(db, R, **cadence, default_machine_id=R.M1.id, next_generation_date=day)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=day)
    # Then 1
    assert pairs(result) == [(day, R.M1.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == after


def test_wtmg_gd_20__monthly_without_day_steps_and_keeps_no_day(db, R):
    """WTMG-GD-20 — monthly with no day from 31 January: 28 February, the day stays empty.
    Rules: generate_drafts R7, R9; recurrence advance_next_generation_date."""
    t = tpl(db, R, is_recurring=True, recurrence_type="monthly", default_machine_id=R.M1.id,
            next_generation_date=date(2026, 1, 31))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=date(2026, 1, 31))
    # Then 1
    assert pairs(result) == [(date(2026, 1, 31), R.M1.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == date(2026, 2, 28)
    # Then 3
    assert reread(db, WorkOrderTemplate, t.id).recurrence_day is None


def test_wtmg_gd_21__section_template_one_draft_per_machine(db, R):
    """WTMG-GD-21 — a template of a section with no default machine: one draft per machine of the section.
    Rules: generate_drafts R6, R7."""
    t = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)


def test_wtmg_gd_22__no_machine_no_draft_date_moves(db, R):
    """WTMG-GD-22 — no machine at all: no draft, but the date still moves.
    Rules: generate_drafts R6, R9."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)
    # Then 3
    assert drafts(db, t.id) == []


def test_wtmg_gd_23__factory_run_gives_factory_machines(db, R):
    """WTMG-GD-23 — a factory run: a template with no section and no machine gets the factory's machines.
    Rules: generate_drafts R6."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16), factory_id=R.F1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)


def test_wtmg_gd_24__factory_run_leaves_out_other_factory_section(db, R):
    """WTMG-GD-24 — a factory run leaves out a due template whose section is in another factory.
    Rules: generate_drafts R1."""
    tpl(db, R, **WEEKLY, next_generation_date=D(16))
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S3.id, next_generation_date=D(16),
            template_name="Boiler check")
    before_v = snap(db, v)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16), factory_id=R.F1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert unchanged_snap(db, v) == before_v
    # Then 3
    assert drafts(db, v.id) == []


def test_wtmg_gd_25__section_run_handles_due_template_once(db, R):
    """WTMG-GD-25 — a section run: a due recurring template of the section is handled once.
    Rules: generate_drafts R1."""
    t = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)
    # Then 3
    assert len(drafts(db, t.id)) == 2


def test_wtmg_gd_26__open_order_no_draft_date_moves(db, R):
    """WTMG-GD-26 — an open order on the machine, day and type: no draft, the date still moves.
    Rules: generate_drafts R7, R9."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    o = order(db, R, "O", R.M1, D(16))
    before_o = snap(db, o)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)
    # Then 3
    assert drafts(db, t.id) == []
    # Then 4
    assert unchanged_snap(db, o) == before_o


@pytest.mark.parametrize("kind", [
    pytest.param("voided", id="WTMG-GD-27"),
    pytest.param("deleted", id="WTMG-GD-28"),
    pytest.param("other_type", id="WTMG-GD-29"),
    pytest.param("other_day", id="WTMG-GD-31"),
    pytest.param("other_machine", id="WTMG-GD-32"),
])
def test_wtmg_gd_27_32__order_that_does_not_block(db, R, kind):
    """WTMG-GD-27, GD-28, GD-29, GD-31, GD-32 — a VOIDED or soft-deleted order, or one of another type, day or
    machine, does not block the draft.
    Rules: generate_drafts R7; Facts (open order)."""
    tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    if kind == "voided":
        o = order(db, R, "O", R.M1, D(16), status="VOIDED")
    elif kind == "deleted":
        o = order(db, R, "O", R.M1, D(16), is_deleted=True, is_active=False, deleted_at=T0, deleted_by=R.U1.id)
    elif kind == "other_type":
        o = order(db, R, "O", R.M1, D(16), work_order_type_id=R.WT2.id)
    elif kind == "other_day":
        o = order(db, R, "O", R.M1, D(15))
    else:
        o = order(db, R, "O", R.M2, D(16))
    before_o = snap(db, o)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 2
    assert unchanged_snap(db, o) == before_o


def test_wtmg_gd_30__completed_order_blocks(db, R):
    """WTMG-GD-30 — a COMPLETED order blocks.
    Rules: generate_drafts R7; Facts (open order)."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    order(db, R, "O", R.M1, D(16), status="COMPLETED")
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert drafts(db, t.id) == []
    # Then 3
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)


def test_wtmg_gd_33__section_machine_with_order_skipped(db, R):
    """WTMG-GD-33 — a section template: the machine with an order is skipped, the other gets its draft.
    Rules: generate_drafts R7, R9."""
    t = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16))
    order(db, R, "O", R.M1, D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M2.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)


def test_wtmg_gd_34__section_run_non_recurring_gets_drafts(db, R):
    """WTMG-GD-34 — a section run: a non-recurring template of the section gets drafts and its dates do not change.
    Rules: generate_drafts R1, R8."""
    n = tpl(db, R, default_factory_section_id=R.S1.id, next_generation_date=D(10))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, n.id).next_generation_date == D(10)
    # Then 3
    assert len(drafts(db, n.id)) == 2


@pytest.mark.parametrize(("given", "scope"), [
    pytest.param({"default_factory_section_id": "S3"}, {"factory_section_id": "S1"}, id="WTMG-GD-35"),
    pytest.param({"default_machine_id": "M1"}, {"factory_section_id": "S1"}, id="WTMG-GD-36"),
    pytest.param({"default_factory_section_id": "S1", "is_active": False}, {"factory_section_id": "S1"},
                 id="WTMG-GD-37"),
    pytest.param({"default_factory_section_id": "S1"}, {}, id="WTMG-GD-38"),
])
def test_wtmg_gd_35_38__non_recurring_template_gets_nothing(db, R, given, scope):
    """WTMG-GD-35 … GD-38 — a non-recurring template of another section, with no section, inactive, or in an
    unscoped run gets nothing.
    Rules: generate_drafts R1, R2."""
    fields = {k: (getattr(R, v).id if isinstance(v, str) else v) for k, v in given.items()}
    n = tpl(db, R, **fields)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               **{k: getattr(R, v).id for k, v in scope.items()})
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert drafts(db, n.id) == []


def test_wtmg_gd_39__section_run_ended_program_skipped(db, R):
    """WTMG-GD-39 — a section run: a recurring template of the section whose program ended is skipped.
    Rules: generate_drafts R5 (after BUG-2345 a guard no input reaches; the outcome is the same either way)."""
    t = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16),
            recurrence_end_date=D(15))
    before = snap(db, t)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert unchanged_snap(db, t) == before
    # Then 3
    assert drafts(db, t.id) == []


def test_wtmg_gd_40__section_template_behind_999_newer(db, R):
    """WTMG-GD-40 — a section run finds the section's oldest template behind 999 newer active ones.
    Rules: generate_drafts R3."""
    tpl(db, R, template_name="Packing check", default_factory_section_id=R.S1.id,
        created_at=datetime(2026, 2, 1, 9, 0, 0))  # noqa: DTZ001
    many_templates(db, R, 999)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]


@xf("BUG-2342")
def test_wtmg_gd_41__section_template_behind_1000_newer(db, R):
    """WTMG-GD-41 — a section run finds the section's oldest template behind 1000 newer active ones.
    Rules: generate_drafts R3 [BUG-2342]."""
    tpl(db, R, template_name="Packing check", default_factory_section_id=R.S1.id,
        created_at=datetime(2026, 2, 1, 9, 0, 0))  # noqa: DTZ001
    many_templates(db, R, 1000)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]


@xf("BUG-2343")
def test_wtmg_gd_42__template_row_locked(db, R):
    """WTMG-GD-42 — unscoped run: the template row is locked before its checks.
    Rules: generate_drafts R11 [BUG-2343]."""
    tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    with record_sql(db) as log:
        result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 2
    assert len(locks_of(log)) >= 1


# [claude] WTMG-GD-43
@xf("BUG-2344")
def test_wtmg_gd_43__one_failure_logged_other_kept(db, R, caplog):
    """WTMG-GD-43 — one template's failure is logged and skipped, the other's draft is kept.
    Rules: generate_drafts R12 [BUG-2344].
    The patch (spec Notes, G6): wom.create_work_order_from_template raises
    RuntimeError("boom") for T1 and calls the real method for every other template."""
    t1 = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    t2 = tpl(db, R, **WEEKLY, default_machine_id=R.M2.id, next_generation_date=D(16), template_name="Belt check")
    t1_id, t2_id = t1.id, t2.id
    real = wom.create_work_order_from_template

    def f(*a, **k):
        template_id = k["template_id"] if "template_id" in k else a[1]
        if template_id == t1_id:
            raise RuntimeError("boom")
        return real(*a, **k)

    caplog.set_level(logging.WARNING)
    # Then 1 (the When sits here: today it raises RuntimeError, so Then 1 is never reached)
    with patch.object(wom, "create_work_order_from_template", side_effect=f):
        result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    assert pairs(result) == [(D(16), R.M2.id)]
    # Then 2
    assert drafts(db, t1_id) == []
    # Then 3
    assert reread(db, WorkOrderTemplate, t1_id).next_generation_date == D(16)
    # Then 4
    assert reread(db, WorkOrderTemplate, t2_id).next_generation_date == D(23)
    # Then 5
    assert any(r.levelno == logging.WARNING and str(t1_id) in r.getMessage() and "boom" in r.getMessage()
               for r in caplog.records)


def test_wtmg_gd_44__foreign_section_selects_nothing(db, R):
    """WTMG-GD-44 — a section of another workspace selects nothing and is not refused, not even that workspace's own
    template.
    Rules: generate_drafts R13, R1."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16),
            template_name="Packing check")
    z9 = tpl_w2(db, R, default_factory_section_id=R.S9.id, default_machine_id=R.M9.id, template_name="Nine check")
    before_t, before_v, before_z9 = snap(db, t), snap(db, v), snap(db, z9)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S9.id)
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert unchanged_snap(db, t) == before_t
    # Then 3
    assert unchanged_snap(db, v) == before_v
    # Then 4
    assert unchanged_snap(db, z9) == before_z9
    # Then 5
    assert drafts(db, z9.id) == []


def test_wtmg_gd_45__unknown_section_selects_nothing(db, R):
    """WTMG-GD-45 — an unknown section selects nothing and is not refused.
    Rules: generate_drafts R13."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16),
            template_name="Packing check")
    before_t, before_v = snap(db, t), snap(db, v)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=MISSING)
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert unchanged_snap(db, t) == before_t
    # Then 3
    assert unchanged_snap(db, v) == before_v


@pytest.mark.parametrize("factory", [
    pytest.param("F9", id="WTMG-GD-46"),
    pytest.param(None, id="WTMG-GD-47"),
])
def test_wtmg_gd_46_47__foreign_or_unknown_factory_finds_no_machine(db, R, factory):
    """WTMG-GD-46 / GD-47 — a factory of another workspace, or an unknown factory: a template with no section or
    machine finds no machine, its date still moves; not refused.
    Rules: generate_drafts R13, R9."""
    t = tpl(db, R, **WEEKLY, next_generation_date=D(16))
    factory_id = R.F9.id if factory else MISSING
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16), factory_id=factory_id)
    # Then 1
    assert pairs(result) == []
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(23)
    # Then 3
    assert drafts(db, t.id) == []


def test_wtmg_gd_48__generate_flushes_never_commits(db, R):
    """WTMG-GD-48 — generate_drafts flushes and never commits.
    Rules: generate_drafts Side effects."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    tid = t.id
    c = WorkOrder.__table__.c
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert len(result) == 1
    # Then 2
    assert n_rows(db, WorkOrder, c.work_order_template_id == tid) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n_rows(db, WorkOrder, c.work_order_template_id == tid) == 0


def test_wtmg_gd_49__draft_carries_account_and_cost(db, R):
    """WTMG-GD-49 — a draft carries the template's account and cost.
    Rules: generate_drafts R7 (spec Facts, G13)."""
    tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16), account_id=R.A1.id,
        cost=Decimal("12.50"))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    first_id = result[0].id
    # Then 2
    first = reread(db, WorkOrder, first_id)
    assert first.account_id == R.A1.id
    assert first.cost == Decimal("12.50")
    assert first.priority == "MEDIUM"
    # Then 3
    first = reread(db, WorkOrder, first_id)
    assert first.created_by == R.U1.id
    assert first.uses_inventory is False


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-19 → BUG-2345 (generate_drafts R1, R4)
# --------------------------------------------------------------------------- #

@xf("BUG-2345")
@pytest.mark.parametrize("given", [
    pytest.param({"next_generation_date": D(16)}, id="WTMG-Q19-01"),
    pytest.param({"next_generation_date": D(16), "default_machine_id": "M1"}, id="WTMG-Q19-02"),
])
def test_wtmg_q19_01_02__not_due_section_template_no_draft(db, R, given):
    """WTMG-Q19-01 / Q19-02 — a recurring template of the section due in six days (with or without a default
    machine) gets no draft; its date stays.
    Rules: generate_drafts R4 [BUG-2345]."""
    fields = {k: (getattr(R, v).id if isinstance(v, str) else v) for k, v in given.items()}
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, **fields)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(10),
                               factory_section_id=R.S1.id)
    # Then 1
    assert reread(db, WorkOrderTemplate, v.id).next_generation_date == D(16)
    # Then 2
    assert pairs(result) == []
    # Then 3
    assert drafts(db, v.id) == []


@xf("BUG-2345")
def test_wtmg_q19_03__never_anchored_section_template_no_draft(db, R):
    """WTMG-Q19-03 — a recurring template of the section never anchored gets no draft; its date stays empty.
    Rules: generate_drafts R4 [BUG-2345]."""
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(10),
                               factory_section_id=R.S1.id)
    # Then 1
    assert reread(db, WorkOrderTemplate, v.id).next_generation_date is None
    # Then 2
    assert pairs(result) == []
    # Then 3
    assert drafts(db, v.id) == []


@xf("BUG-2345")
def test_wtmg_q19_04__next_day_section_run_no_more_drafts(db, R):
    """WTMG-Q19-04 — planning the section again the next day gives no more drafts.
    Rules: generate_drafts R4 [BUG-2345]."""
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16))
    order(db, R, "A", R.M1, D(10), work_order_template_id=v.id)
    order(db, R, "B", R.M2, D(10), work_order_template_id=v.id)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(11),
                               factory_section_id=R.S1.id)
    # Then 1
    assert reread(db, WorkOrderTemplate, v.id).next_generation_date == D(16)
    # Then 2
    assert pairs(result) == []
    # Then 3
    assert len(drafts(db, v.id)) == 2


def test_wtmg_q19_05__section_run_before_due_leaves_date(db, R):
    """WTMG-Q19-05 — a section run before the due date leaves the template's date alone.
    Rules: generate_drafts R4, R8."""
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16),
            recurrence_end_date=D(30))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(10),
                               factory_section_id=R.S1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    row = reread(db, WorkOrderTemplate, v.id)
    assert row.next_generation_date == D(16)
    assert row.recurrence_end_date == D(30)


def test_wtmg_q19_06__due_day_one_draft_per_machine_once(db, R):
    """WTMG-Q19-06 — on its due day a recurring template of the section gets one draft per machine, once, and moves.
    Rules: generate_drafts R1, R4, R9."""
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 2
    assert drafts(db, v.id) == [(D(16), R.M1.id), (D(16), R.M2.id)]
    # Then 3
    assert reread(db, WorkOrderTemplate, v.id).next_generation_date == D(23)


@xf("BUG-2345")
def test_wtmg_q19_07__due_tomorrow_section_template_no_draft(db, R):
    """WTMG-Q19-07 — a recurring template of the section due tomorrow gets no draft; its date stays.
    Rules: generate_drafts R4 [BUG-2345]."""
    v = tpl(db, R, **WEEKLY, default_factory_section_id=R.S1.id, next_generation_date=D(17))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16),
                               factory_section_id=R.S1.id)
    # Then 1
    assert reread(db, WorkOrderTemplate, v.id).next_generation_date == D(17)
    # Then 2
    assert pairs(result) == []
    # Then 3
    assert drafts(db, v.id) == []


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-20 ✅ intended (generate_drafts R10)
# --------------------------------------------------------------------------- #

def test_wtmg_q20_01__late_weekly_run_one_draft(db, R):
    """WTMG-Q20-01 — weekly due 16 March, run 30 March: one draft for the 30th, next date 6 April.
    Rules: generate_drafts R10 (owner, OQ-20)."""
    t = tpl(db, R, **WEEKLY, default_machine_id=R.M1.id, next_generation_date=D(16))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(30))
    # Then 1
    assert pairs(result) == [(D(30), R.M1.id)]
    # Then 2
    assert drafts(db, t.id) == [(D(30), R.M1.id)]
    # Then 3
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == date(2026, 4, 6)


def test_wtmg_q20_02__late_daily_run_one_draft(db, R):
    """WTMG-Q20-02 — daily due 10 March, run 16 March: one draft, next date 17 March.
    Rules: generate_drafts R10 (owner, OQ-20)."""
    t = tpl(db, R, **DAILY, default_machine_id=R.M1.id, next_generation_date=D(10))
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=D(16))
    # Then 1
    assert pairs(result) == [(D(16), R.M1.id)]
    # Then 2
    assert drafts(db, t.id) == [(D(16), R.M1.id)]
    # Then 3
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(17)


@pytest.mark.parametrize(("cadence", "due", "run", "after"), [
    pytest.param(monthly(15), date(2026, 1, 15), D(20), date(2026, 4, 15), id="WTMG-Q20-03"),
    pytest.param(WEEKLY, D(16), D(18), D(23), id="WTMG-Q20-04"),
])
def test_wtmg_q20_03_04__late_run_steps_from_run_day(db, R, cadence, due, run, after):
    """WTMG-Q20-03 / Q20-04 — a late run steps the next date from the run's day.
    Rules: generate_drafts R10 (owner, OQ-20)."""
    t = tpl(db, R, **cadence, default_machine_id=R.M1.id, next_generation_date=due)
    result = M.generate_drafts(db, workspace_id=R.W1.id, user_id=R.U1.id, target_date=run)
    # Then 1
    assert pairs(result) == [(run, R.M1.id)]
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == after


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-21 → BUG-2346 (create_template R6, update_template R9)
# --------------------------------------------------------------------------- #

@xf("BUG-2346")
def test_wtmg_q21_01__create_requires_approval_without_approvers(db, R):
    """WTMG-Q21-01 — create: requires approval with no approvers given is refused, nothing written.
    Rules: create_template R6 [BUG-2346], Errors row 5."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=R.WT1.id,
                                      requires_approval=True),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDS_APPROVER
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


@xf("BUG-2346")
def test_wtmg_q21_02__create_requires_approval_empty_list(db, R):
    """WTMG-Q21-02 — create: requires approval with an empty approver list is refused, nothing written.
    Rules: create_template R6 [BUG-2346], Errors row 5."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=R.WT1.id,
                                      requires_approval=True, uses_inventory=True, items=[IC(item_id=R.I1.id)],
                                      approver_user_ids=[]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDS_APPROVER
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_q21_03__approvers_without_requires_approval_stored(db, R):
    """WTMG-Q21-03 — create: approvers given without requires approval are stored.
    Rules: create_template R6a."""
    result = M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=R.WT1.id,
                                           requires_approval=False, approver_user_ids=[R.U1.id]),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    assert reread(db, WorkOrderTemplate, rid).requires_approval is False
    # Then 3
    assert approvers(db, R, result) == [R.U1.id]


@xf("BUG-2346")
def test_wtmg_q21_04__update_removing_every_approver_refused(db, R):
    """WTMG-Q21-04 — update: removing every approver while requires approval stays true is refused.
    Rules: update_template R9 [BUG-2346]."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=[]), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDS_APPROVER
    # Then 3
    assert not db.new
    # Then 4
    assert not db.deleted
    # Then 5
    assert unchanged_snap(db, t) == before
    # Then 6
    assert approvers(db, R, t) == [R.U1.id]


@xf("BUG-2346")
def test_wtmg_q21_05__update_turning_on_without_approvers_refused(db, R):
    """WTMG-Q21-05 — update: turning requires approval on with no approvers is refused.
    Rules: update_template R9 [BUG-2346]."""
    t = tpl(db, R)
    before = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(requires_approval=True), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDS_APPROVER
    # Then 3
    assert not db.dirty
    # Then 4
    assert unchanged_snap(db, t) == before
    # Then 5
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.requires_approval is False
    assert row.updated_by is None


def test_wtmg_q21_07__old_template_without_approvers_renamed(db, R):
    """WTMG-Q21-07 — an old template that requires approval with no approvers can still be renamed.
    Rules: update_template R9 (a request sending neither field is not checked)."""
    t = tpl(db, R, requires_approval=True)
    result = M.update_template(db, tpl_id=t.id, data=TU(template_name="Boiler check", notes="Yearly"),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = reread(db, WorkOrderTemplate, t.id)
    assert row.template_name == "Boiler check"
    assert row.notes == "Yearly"
    assert row.requires_approval is True
    # Then 3
    assert approvers(db, R, t) == []


@xf("BUG-2335")
def test_wtmg_q21_08__suspended_only_approver_refused_first(db, R):
    """WTMG-Q21-08 — create: requires approval with only a suspended approver gets the approver refusal first.
    Rules: create_template R5 [BUG-2335], R10; R6."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=R.WT1.id,
                                      requires_approval=True, approver_user_ids=[R.U4.id]),
                          workspace_id=R.W1.id, user_id=R.U1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == ACTIVE_DETAIL
    # Then 3
    assert not db.new
    # Then 4
    assert counts(db) == before


def test_wtmg_q21_09__requires_approval_with_one_approver_accepted(db, R):
    """WTMG-Q21-09 — create: requires approval with one active approver is accepted.
    Rules: create_template R6, R5."""
    result = M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=R.WT1.id,
                                           requires_approval=True, approver_user_ids=[R.U2.id]),
                               workspace_id=R.W1.id, user_id=R.U1.id)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    assert reread(db, WorkOrderTemplate, rid).requires_approval is True
    # Then 3
    assert approvers(db, R, result) == [R.U2.id]


def test_wtmg_q21_10__stored_suspended_approver_counts(db, R):
    """WTMG-Q21-10 — update: turning requires approval on counts a stored approver who has since been suspended.
    Rules: update_template R9 (stored approvers count whatever their membership is now)."""
    t = tpl(db, R)
    approver(db, R, t, R.U4)
    result = M.update_template(db, tpl_id=t.id, data=TU(requires_approval=True), workspace_id=R.W1.id,
                               user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).requires_approval is True
    # Then 3
    assert approvers(db, R, t) == [R.U4.id]


def test_wtmg_q21_11__turning_off_and_removing_all_accepted(db, R):
    """WTMG-Q21-11 — update: turning requires approval off and removing every approver together is accepted.
    Rules: update_template R9, R8."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    result = M.update_template(db, tpl_id=t.id, data=TU(requires_approval=False, approver_user_ids=[]),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).requires_approval is False
    # Then 3
    assert approvers(db, R, t) == []


@xf("BUG-2346")
def test_wtmg_q21_12__null_approvers_on_requires_approval_refused(db, R):
    """WTMG-Q21-12 — update: approvers sent as null on a template that requires approval is refused.
    Rules: update_template R9 [BUG-2346], R8."""
    t = tpl(db, R, requires_approval=True)
    approver(db, R, t, R.U1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=TU(approver_user_ids=None), workspace_id=R.W1.id, user_id=R.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDS_APPROVER
    # Then 3
    assert not db.deleted
    # Then 4
    assert approvers(db, R, t) == [R.U1.id]


def test_wtmg_q21_13__turning_on_with_one_approver_accepted(db, R):
    """WTMG-Q21-13 — update: turning requires approval on together with one active approver is accepted.
    Rules: update_template R9, R8."""
    t = tpl(db, R)
    result = M.update_template(db, tpl_id=t.id, data=TU(requires_approval=True, approver_user_ids=[R.U2.id]),
                               workspace_id=R.W1.id, user_id=R.U2.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert reread(db, WorkOrderTemplate, t.id).requires_approval is True
    # Then 3
    assert approvers(db, R, t) == [R.U2.id]
