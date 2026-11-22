"""Unit tests for app/services/work_order_template_service.py.

Implements tests/unit/services/work_order_template_service.cases.md (revision 3),
one test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Nothing is patched except what
Conventions name: the failing commit / failing refresh wraps, the commit /
rollback spies, and the `Author: claude` cards' patches (GD-03 the manager's
`generate_drafts`, GD-04 `work_order_manager.create_work_order_from_template`).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows are attributes of the `s` fixture (`W1.id` -> `s.W1.id`);
Given rows keep the card's names in lower case; `# Then N` marks the checks of
the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text

from app.managers.work_order_manager import work_order_manager
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order import WorkOrder
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from app.schemas.work_order_template import (
    GenerateWorkOrderDraftsRequest,
    WorkOrderTemplateCreate,
    WorkOrderTemplateItemCreate,
    WorkOrderTemplateItemUpdate,
    WorkOrderTemplateUpdate,
)
from app.services.work_order_template_service import work_order_template_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton work_order_template_service"
svc = work_order_template_service

MISSING = 999999999
T0 = datetime(2026, 3, 4, 9, 0, 0)
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 4, 11, 0, 0)
T3 = datetime(2026, 3, 4, 12, 0, 0)
D16 = date(2026, 3, 16)
D17 = date(2026, 3, 17)
D23 = date(2026, 3, 23)
D30 = date(2026, 3, 30)

APPROVER_NEEDED = 'Choose at least one approver, or turn off "requires approval"'
NOT_ACTIVE = "User is not an active member of this workspace"


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in the card's order)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def s(db):
    """W0, W1, W2; U1, U2; MB1, MB2; WT0, WT1, WT2; I1, I2."""
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db)
    n.U2 = make_profile(db)
    n.MB1 = _add(db, WorkspaceMember(workspace_id=n.W1.id, user_id=n.U1.id, role="member", status="active"))
    n.MB2 = _add(db, WorkspaceMember(workspace_id=n.W1.id, user_id=n.U2.id, role="member", status="active"))
    n.WT0 = _add(db, WorkOrderType(workspace_id=n.W0.id, name="Service"))
    n.WT1 = _add(db, WorkOrderType(workspace_id=n.W1.id, name="Service"))
    n.WT2 = _add(db, WorkOrderType(workspace_id=n.W2.id, name="Service"))
    n.I1 = _add(db, Item(workspace_id=n.W1.id, name="Oil filter", name_normalized="oil filter", unit="pcs"))
    n.I2 = _add(db, Item(workspace_id=n.W1.id, name="Belt", name_normalized="belt", unit="pcs"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "template" (after "but": the differing columns)
def mk_tpl(db, s, **but):
    fields = {
        "workspace_id": s.W1.id, "template_name": "Oil change", "work_order_type_id": s.WT1.id,
        "created_by": s.U2.id, "created_at": T0,
    }
    fields.update(but)
    return _add(db, WorkOrderTemplate(**fields))


# Convention "inactive" (after "but")
def inactive(s):
    return {"is_active": False, "updated_by": s.U2.id, "updated_at": T0}


# Convention "recurring" (after "but")
def recurring(p):
    return {"is_recurring": True, "recurrence_type": "weekly", "next_generation_date": D16,
            "default_machine_id": p.M1.id}


# Convention "line on T"
def mk_line(db, s, t, **but):
    fields = {"workspace_id": s.W1.id, "work_order_template_id": t.id, "item_id": s.I1.id,
              "quantity": Decimal("2.00")}
    fields.update(but)
    return _add(db, WorkOrderTemplateItem(**fields))


# Convention "approver U on T"
def mk_approver(db, s, t, u):
    return _add(db, WorkOrderTemplateApprover(workspace_id=s.W1.id, work_order_template_id=t.id, user_id=u.id))


# Convention "plant": F1, S1, M1 and M1's assignment to S1
def mk_plant(db, s):
    p = SimpleNamespace()
    p.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Plant", abbreviation="PL"))
    p.S1 = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=p.F1.id, name="Packing"))
    p.M1 = _add(db, Machine(workspace_id=s.W1.id, factory_id=p.F1.id, name="Press 1"))
    _add(db, MachineSectionAssignment(workspace_id=s.W1.id, machine_id=p.M1.id, factory_section_id=p.S1.id))
    return p


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X": returns X_ID
def extra_x(db, s):
    x = _add(db, WorkOrderTemplate(workspace_id=s.W2.id, template_name="Extra", work_order_type_id=s.WT2.id,
                                   created_at=T0))
    return x.id


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def _columns(db, model, row_id):
    table = model.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, type(row), _id_of(row))


# ... and after a re-read
def snap(db, model, row_id):
    db.expire_all()
    return _columns(db, model, row_id)


def count(db, model, **filters):
    query = select(func.count()).select_from(model)
    for column, value in filters.items():
        query = query.where(getattr(model, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return (count(db, WorkOrderTemplate), count(db, WorkOrderTemplateItem),
            count(db, WorkOrderTemplateApprover), count(db, WorkOrder))


# Convention "approvers(T)"
def approvers(db, tpl_id):
    db.expire_all()
    return {a.user_id for a in db.scalars(
        select(WorkOrderTemplateApprover).where(WorkOrderTemplateApprover.work_order_template_id == tpl_id))}


# Convention "drafts(T)"
def drafts(db, tpl_id):
    return count(db, WorkOrder, work_order_template_id=tpl_id)


# Convention "x_gone" / "x_kept": the number of rows with id X_ID
def x_rows(db, x_id):
    return count(db, WorkOrderTemplate, id=x_id)


# Convention "loaded:"
def unloaded(obj):
    return inspect(obj).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.create_template
# --------------------------------------------------------------------------- #

# [claude] WTSV-C-01
def test_wtsv_c_01__the_template_its_line_and_its_approver_are_committed(db, s):
    """WTSV-C-01 — the template, its line and its approver are committed; the template returned re-read.
    Rules: `create_template` R1; TC1, TC2"""
    commit_point(db)
    result = svc.create_template(db, tpl_in=WorkOrderTemplateCreate(
        template_name="Oil change", work_order_type_id=s.WT1.id, cost=Decimal("12.50"), requires_approval=True,
        items=[WorkOrderTemplateItemCreate(item_id=s.I1.id, quantity=Decimal(2))],
        approver_user_ids=[s.U2.id]), workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    for col in ("created_at", "template_name", "work_order_type_id", "cost", "created_by"):
        assert col not in unloaded(result)
    # Then 2
    assert isinstance(result, WorkOrderTemplate)
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.template_name == "Oil change"
    assert result.workspace_id == s.W1.id
    assert result.created_by == s.U1.id
    assert result.is_active is True
    # Then 4
    rid = result.id
    db.rollback()
    row = reread(db, WorkOrderTemplate, rid)
    assert row is not None
    assert row.cost == Decimal("12.50")
    assert row.work_order_type_id == s.WT1.id
    # Then 5
    lines = db.scalars(select(WorkOrderTemplateItem).where(WorkOrderTemplateItem.work_order_template_id == rid)).all()
    assert len(lines) == 1
    assert lines[0].item_id == s.I1.id
    assert lines[0].quantity == Decimal("2.00")
    assert lines[0].action_type == "CONSUME"
    # Then 6
    assert approvers(db, rid) == {s.U2.id}


# [claude] WTSV-C-02
def test_wtsv_c_02__a_type_of_another_workspace_higher_id_404_nothing_saved(db, s):
    """WTSV-C-02 — a type of another workspace (higher id): the 404 passes unchanged; no template, line or approver saved.
    Rules: `create_template` R2; TC3"""
    commit_point(db)
    before = written(db)
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=WorkOrderTemplateCreate(
            template_name="Oil change", work_order_type_id=s.WT2.id, requires_approval=True,
            items=[WorkOrderTemplateItemCreate(item_id=s.I1.id)], approver_user_ids=[s.U2.id]),
            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order type with ID {s.WT2.id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] WTSV-C-03
def test_wtsv_c_03__a_type_of_another_workspace_lower_id_404_nothing_saved(db, s):
    """WTSV-C-03 — a type of another workspace (lower id): 404, nothing saved.
    Rules: `create_template` R2; TC3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=s.WT0.id),
                            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order type with ID {s.WT0.id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] WTSV-C-04
def test_wtsv_c_04__a_failing_commit_is_rolled_back_and_re_raised(db, s):
    """WTSV-C-04 — a failing commit is rolled back and re-raised; nothing is saved.
    Rules: `create_template` R3; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_template(db, tpl_in=WorkOrderTemplateCreate(
                template_name="Oil change", work_order_type_id=s.WT1.id,
                items=[WorkOrderTemplateItemCreate(item_id=s.I1.id)]), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count(db, WorkOrderTemplate, workspace_id=s.W1.id) == 0
    # Then 4
    assert count(db, WorkOrderTemplateItem, workspace_id=s.W1.id) == 0


# [claude] WTSV-C-05
def test_wtsv_c_05__a_failing_re_read_after_the_commit_leaves_the_template_saved(db, s):
    """WTSV-C-05 — a failing re-read after the commit leaves the template saved.
    Rules: `create_template` R3; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change",
                                                                   work_order_type_id=s.WT1.id),
                                workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    db.expire_all()
    rows = db.scalars(select(WorkOrderTemplate).where(WorkOrderTemplate.workspace_id == s.W1.id)).all()
    assert len(rows) == 1
    assert rows[0].template_name == "Oil change"
    assert rows[0].created_by == s.U1.id


# [claude] WTSV-C-06
@pytest.mark.xfail(strict=True, reason="BUG-1228: A soft-deleted work order type can be chosen for new work orders and templates")
def test_wtsv_c_06__pass_through_bug_1228_a_deleted_type_is_refused(db, s):
    """WTSV-C-06 — pass-through BUG-1228: a deleted type of the workspace is refused.
    Rules: `create_template` R2 [BUG-1228]"""
    wtd = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Old", is_deleted=True, deleted_at=T0,
                                 deleted_by=s.U2.id))
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=wtd.id),
                            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order type with ID {wtd.id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] WTSV-C-07
@pytest.mark.xfail(strict=True, reason="BUG-2335: Template approvers who cannot approve are dropped without a word")
def test_wtsv_c_07__pass_through_bug_2335_a_suspended_approver_refuses_the_create(db, s):
    """WTSV-C-07 — pass-through BUG-2335: a suspended approver refuses the whole create.
    Rules: `create_template` R2 [BUG-2335]"""
    u3 = make_profile(db)
    _add(db, WorkspaceMember(workspace_id=s.W1.id, user_id=u3.id, role="member", status="suspended"))
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=WorkOrderTemplateCreate(
            template_name="Oil change", work_order_type_id=s.WT1.id, requires_approval=True,
            items=[WorkOrderTemplateItemCreate(item_id=s.I1.id)], approver_user_ids=[s.U2.id, u3.id]),
            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == NOT_ACTIVE
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] WTSV-C-08
@pytest.mark.xfail(strict=True, reason="BUG-2334: Blank work order template name accepted")
def test_wtsv_c_08__pass_through_bug_2334_the_name_is_stored_trimmed(db, s):
    """WTSV-C-08 — pass-through BUG-2334: the name is stored trimmed.
    Rules: `create_template` R1 [BUG-2334]"""
    commit_point(db)
    result = svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="  Oil change ",
                                                                    work_order_type_id=s.WT1.id),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert result.template_name == "Oil change"
    # Then 3
    rid = result.id
    db.rollback()
    assert reread(db, WorkOrderTemplate, rid).template_name == "Oil change"


# [claude] WTSV-C-09
@pytest.mark.xfail(strict=True, reason="BUG-2346: A template that \"requires approval\" but has no approvers gives orders approved at once")
def test_wtsv_c_09__pass_through_bug_2346_requires_approval_with_no_approver_refused(db, s):
    """WTSV-C-09 — pass-through BUG-2346: "requires approval" with no approver is refused; nothing saved.
    Rules: `create_template` R2a [BUG-2346]"""
    commit_point(db)
    before = written(db)
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=WorkOrderTemplateCreate(
            template_name="Oil change", work_order_type_id=s.WT1.id, requires_approval=True,
            items=[WorkOrderTemplateItemCreate(item_id=s.I1.id)]), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == APPROVER_NEEDED
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert written(db) == before


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.update_template
# --------------------------------------------------------------------------- #

# [claude] WTSV-U-01
def test_wtsv_u_01__the_change_is_committed_and_returned_re_read_cost_rounds_half_up(db, s):
    """WTSV-U-01 — the change is committed and returned re-read; cost rounds half up in the column.
    Rules: `update_template` R1; TC1, TC2"""
    t = mk_tpl(db, s)
    commit_point(db)
    result = svc.update_template(db, tpl_id=t.id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check",
                                                                                 cost=Decimal("0.125")),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    for col in ("updated_at", "template_name", "cost", "updated_by"):
        assert col not in unloaded(result)
    # Then 2
    assert result.id == t.id
    assert result.template_name == "Belt check"
    assert result.cost == Decimal("0.13")
    # Then 3
    assert result.updated_at is not None
    assert result.updated_by == s.U1.id
    # Then 4
    tid = t.id
    db.rollback()
    row = reread(db, WorkOrderTemplate, tid)
    assert row.template_name == "Belt check"
    assert row.cost == Decimal("0.13")
    assert row.updated_by == s.U1.id


# [claude] WTSV-U-02
def test_wtsv_u_02__another_workspaces_id_higher_404_pending_changes_discarded(db, s):
    """WTSV-U-02 — another workspace's id (higher): the 404 passes unchanged; pending changes discarded.
    Rules: `update_template` R2; TC3"""
    t = mk_tpl(db, s)
    z = mk_tpl(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    before_t = snap_before(db, t)
    z_id, t_id = z.id, t.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_template(db, tpl_id=z_id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check"),
                            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order template with ID {z_id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert snap(db, WorkOrderTemplate, z_id) == before_z
    # Then 6
    assert snap(db, WorkOrderTemplate, t_id) == before_t


# [claude] WTSV-U-03
@pytest.mark.xfail(strict=True, reason="BUG-2335: Template approvers who cannot approve are dropped without a word")
def test_wtsv_u_03__pass_through_bug_2335_an_approver_refusal_undoes_the_fields(db, s):
    """WTSV-U-03 — pass-through BUG-2335: an approver refusal undoes the fields already written.
    Rules: `update_template` R2 [BUG-2335]"""
    u3 = make_profile(db)
    _add(db, WorkspaceMember(workspace_id=s.W1.id, user_id=u3.id, role="member", status="suspended"))
    t = mk_tpl(db, s, requires_approval=True)
    mk_approver(db, s, t, s.U2)
    commit_point(db)
    t_id = t.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_template(db, tpl_id=t_id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check",
                                                                            approver_user_ids=[s.U2.id, u3.id]),
                            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == NOT_ACTIVE
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    row = reread(db, WorkOrderTemplate, t_id)
    assert row.template_name == "Oil change"
    assert row.updated_by is None
    # Then 5
    assert approvers(db, t_id) == {s.U2.id}


# [claude] WTSV-U-04
@pytest.mark.xfail(strict=True, reason="BUG-2340: Template \"updated by\" stamped when nothing changed")
def test_wtsv_u_04__pass_through_bug_2340_an_empty_update_leaves_updated_by(db, s):
    """WTSV-U-04 — pass-through BUG-2340: an empty update leaves `updated_by` as it was.
    Rules: `update_template` R3 [BUG-2340]"""
    t = mk_tpl(db, s, updated_by=s.U2.id, updated_at=T0)
    commit_point(db)
    t_id = t.id
    result = svc.update_template(db, tpl_id=t_id, tpl_in=WorkOrderTemplateUpdate(), workspace_id=s.W1.id,
                                 user_id=s.U1.id)
    # Then 1
    assert result.id == t_id
    # Then 2
    db.rollback()
    assert reread(db, WorkOrderTemplate, t_id).updated_by == s.U2.id
    # Then 3
    assert reread(db, WorkOrderTemplate, t_id).updated_at == T0


# [claude] WTSV-U-05
def test_wtsv_u_05__a_new_approver_list_replaces_the_old_one(db, s):
    """WTSV-U-05 — a new approver list replaces the old one and is committed.
    Rules: `update_template` R1; TC1"""
    t = mk_tpl(db, s, requires_approval=True)
    mk_approver(db, s, t, s.U2)
    commit_point(db)
    t_id = t.id
    result = svc.update_template(db, tpl_id=t_id, tpl_in=WorkOrderTemplateUpdate(approver_user_ids=[s.U1.id]),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result.id == t_id
    # Then 2
    db.rollback()
    assert approvers(db, t_id) == {s.U1.id}


# [claude] WTSV-U-06
@pytest.mark.xfail(strict=True, reason="BUG-2346: A template that \"requires approval\" but has no approvers gives orders approved at once")
def test_wtsv_u_06__pass_through_bug_2346_requires_approval_on_update_with_no_approver(db, s):
    """WTSV-U-06 — pass-through BUG-2346: turning on "requires approval" with no approver is refused; nothing saved.
    Rules: `create_template` R2a (update) [BUG-2346]"""
    t = mk_tpl(db, s)
    commit_point(db)
    before_t = snap_before(db, t)
    t_id = t.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_template(db, tpl_id=t_id, tpl_in=WorkOrderTemplateUpdate(requires_approval=True),
                            workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == APPROVER_NEEDED
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert snap(db, WorkOrderTemplate, t_id) == before_t


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.get_template
# --------------------------------------------------------------------------- #

# [claude] WTSV-G-01
def test_wtsv_g_01__an_inactive_template_is_returned_no_commit_no_rollback(db, s):
    """WTSV-G-01 — an inactive template is returned; the read neither commits nor rolls back.
    Rules: `get_template` R1, R2; TC6"""
    t = mk_tpl(db, s, **inactive(s))
    commit_point(db)
    x_id = extra_x(db, s)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_template(db, tpl_id=t.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == t.id
    assert result.is_active is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_rows(db, x_id) == 1


# [claude] WTSV-G-02
def test_wtsv_g_02__another_workspaces_id_lower_404_nothing_rolled_back(db, s):
    """WTSV-G-02 — another workspace's id (lower): the 404 passes unchanged, nothing rolled back.
    Rules: `get_template` R1, R2; TC6"""
    z = mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id)
    mk_tpl(db, s)
    commit_point(db)
    x_id = extra_x(db, s)
    with pytest.raises(HTTPException) as exc:
        with patch.object(db, "commit", wraps=db.commit), patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.get_template(db, tpl_id=z.id, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_rows(db, x_id) == 1


# [claude] WTSV-G-03
def test_wtsv_g_03__another_workspaces_id_higher_404(db, s):
    """WTSV-G-03 — another workspace's id (higher): 404.
    Rules: `get_template` R1"""
    mk_tpl(db, s)
    z = mk_tpl(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT2.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_template(db, tpl_id=z.id, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Work order template with ID {z.id} not found"


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.list_templates
# --------------------------------------------------------------------------- #

# [claude] WTSV-L-01
def test_wtsv_l_01__all_five_arguments_reach_the_manager(db, s):
    """WTSV-L-01 — all five arguments reach the manager.
    Rules: `list_templates` R1"""
    wtb = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Repair"))
    a = mk_tpl(db, s, **inactive(s), created_at=T1)
    mk_tpl(db, s, **inactive(s), template_name="Belt check", created_at=T2)
    mk_tpl(db, s, template_name="Grease", created_at=T3)
    mk_tpl(db, s, **inactive(s), template_name="Paint", work_order_type_id=wtb.id, created_at=T3)
    mk_tpl(db, s, **inactive(s), template_name="Valve", created_at=T0)
    commit_point(db)
    result = svc.list_templates(db, workspace_id=s.W1.id, is_active=False, work_order_type_id=s.WT1.id, skip=1,
                                limit=1)
    # Then 1
    assert [t.id for t in result] == [a.id]


# [claude] WTSV-L-02
def test_wtsv_l_02__the_default_lists_both_states_of_the_workspace_only(db, s):
    """WTSV-L-02 — the default lists both states, of the workspace only.
    Rules: `list_templates` R1"""
    mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id, created_at=T3)
    a = mk_tpl(db, s, created_at=T1)
    b = mk_tpl(db, s, **inactive(s), template_name="Belt check", created_at=T2)
    mk_tpl(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT2.id, created_at=T3)
    commit_point(db)
    result = svc.list_templates(db, workspace_id=s.W1.id)
    # Then 1
    assert {t.id for t in result} == {a.id, b.id}
    # Then 2
    assert len(result) == 2


# [claude] WTSV-L-03
def test_wtsv_l_03__the_list_neither_commits_nor_rolls_back(db, s):
    """WTSV-L-03 — the list neither commits nor rolls back.
    Rules: `list_templates` R2; TC6"""
    a = mk_tpl(db, s)
    commit_point(db)
    x_id = extra_x(db, s)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.list_templates(db, workspace_id=s.W1.id)
    # Then 1
    assert [t.id for t in result] == [a.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_rows(db, x_id) == 1


# [claude] WTSV-L-04
def test_wtsv_l_04__with_no_limit_101_templates_give_the_newest_100(db, s):
    """WTSV-L-04 — with no limit, 101 templates give the newest 100.
    Rules: `list_templates` R1"""
    rows = [WorkOrderTemplate(workspace_id=s.W1.id, template_name=f"Oil change {k}", work_order_type_id=s.WT1.id,
                              created_by=s.U2.id, created_at=T0 + timedelta(minutes=k)) for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    commit_point(db)
    newest = [r.id for r in reversed(rows)]
    result = svc.list_templates(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert [t.id for t in result] == newest[:100]


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.delete_template
# --------------------------------------------------------------------------- #

# [claude] WTSV-D-01
def test_wtsv_d_01__an_active_template_is_deactivated_lines_and_approvers_stay(db, s):
    """WTSV-D-01 — an active template is deactivated and committed; None; lines and approvers stay.
    Rules: `delete_template` R1, Returns; TC1"""
    t = mk_tpl(db, s, requires_approval=True)
    line = mk_line(db, s, t)
    mk_approver(db, s, t, s.U2)
    commit_point(db)
    t_id, l_id = t.id, line.id
    result = svc.delete_template(db, tpl_id=t_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    row = reread(db, WorkOrderTemplate, t_id)
    assert row.is_active is False
    assert row.updated_by == s.U1.id
    # Then 3
    lrow = reread(db, WorkOrderTemplateItem, l_id)
    assert lrow is not None
    assert lrow.quantity == Decimal("2.00")
    # Then 4
    assert approvers(db, t_id) == {s.U2.id}


# [claude] WTSV-D-02
def test_wtsv_d_02__an_inactive_template_none_nothing_new_committed(db, s):
    """WTSV-D-02 — an inactive template: None, nothing new committed.
    Rules: `delete_template` R1"""
    t = mk_tpl(db, s, **inactive(s))
    commit_point(db)
    before_t = snap_before(db, t)
    t_id = t.id
    result = svc.delete_template(db, tpl_id=t_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert snap(db, WorkOrderTemplate, t_id) == before_t
    # Then 3
    row = reread(db, WorkOrderTemplate, t_id)
    assert row.updated_by == s.U2.id
    assert row.updated_at == T0


# [claude] WTSV-D-03
def test_wtsv_d_03__another_workspaces_id_lower_404_after_a_rollback(db, s):
    """WTSV-D-03 — another workspace's id (lower): the 404 passes unchanged after a rollback.
    Rules: `delete_template` R2; TC3"""
    z = mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id)
    mk_tpl(db, s)
    commit_point(db)
    before_z = snap_before(db, z)
    z_id = z.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_template(db, tpl_id=z_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order template with ID {z_id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert snap(db, WorkOrderTemplate, z_id) == before_z


# [claude] WTSV-D-04
def test_wtsv_d_04__a_failing_commit_rolled_back_the_template_stays_active(db, s):
    """WTSV-D-04 — a failing commit: rolled back, re-raised, the template stays active.
    Rules: `delete_template` R2; TC4"""
    t = mk_tpl(db, s)
    commit_point(db)
    t_id = t.id
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_template(db, tpl_id=t_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, WorkOrderTemplate, t_id)
    assert row.is_active is True
    assert row.updated_by is None


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.restore_template
# --------------------------------------------------------------------------- #

# [claude] WTSV-S-01
def test_wtsv_s_01__an_inactive_template_is_restored_committed_and_returned(db, s):
    """WTSV-S-01 — an inactive template is restored, committed and returned re-read.
    Rules: `restore_template` R1, Returns; TC1, TC2"""
    t = mk_tpl(db, s, **inactive(s))
    commit_point(db)
    t_id = t.id
    result = svc.restore_template(db, tpl_id=t_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    for col in ("is_active", "updated_by", "updated_at"):
        assert col not in unloaded(result)
    # Then 2
    assert result.id == t_id
    assert result.is_active is True
    assert result.updated_by == s.U1.id
    # Then 3
    db.rollback()
    row = reread(db, WorkOrderTemplate, t_id)
    assert row.is_active is True
    assert row.updated_by == s.U1.id


# [claude] WTSV-S-02
def test_wtsv_s_02__another_workspaces_id_higher_404_nothing_saved(db, s):
    """WTSV-S-02 — another workspace's id (higher): 404 unchanged, nothing saved.
    Rules: `restore_template` R2; TC3"""
    z = mk_tpl(db, s, **inactive(s), workspace_id=s.W2.id, work_order_type_id=s.WT2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    z_id = z.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.restore_template(db, tpl_id=z_id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Work order template with ID {z_id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert snap(db, WorkOrderTemplate, z_id) == before_z


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.add_item
# --------------------------------------------------------------------------- #

# [claude] WTSV-A-01
def test_wtsv_a_01__the_new_line_is_committed_and_returned_re_read(db, s):
    """WTSV-A-01 — the new line is committed and returned re-read.
    Rules: `add_item` R1; TC1, TC2"""
    t = mk_tpl(db, s)
    commit_point(db)
    t_id = t.id
    result = svc.add_item(db, tpl_id=t_id, item_in=WorkOrderTemplateItemCreate(
        item_id=s.I2.id, quantity=Decimal(3), action_type="INSTALL"), workspace_id=s.W1.id)
    # Then 1
    for col in ("quantity", "action_type", "item_id"):
        assert col not in unloaded(result)
    # Then 2
    assert isinstance(result, WorkOrderTemplateItem)
    assert result.work_order_template_id == t_id
    assert result.quantity == Decimal("3.00")
    # Then 3
    rid = result.id
    db.rollback()
    row = reread(db, WorkOrderTemplateItem, rid)
    assert row is not None
    assert row.item_id == s.I2.id
    assert row.action_type == "INSTALL"
    assert row.workspace_id == s.W1.id


# [claude] WTSV-A-02
def test_wtsv_a_02__replace_with_no_replaced_item_400_nothing_saved(db, s):
    """WTSV-A-02 — REPLACE with no replaced item: the 400 passes unchanged; nothing saved.
    Rules: `add_item` R2; TC3"""
    t = mk_tpl(db, s)
    commit_point(db)
    before = written(db)
    t_id = t.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, tpl_id=t_id, item_in=WorkOrderTemplateItemCreate(item_id=s.I1.id, action_type="REPLACE"),
                     workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select the item being replaced"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert written(db) == before


# [claude] WTSV-A-03
def test_wtsv_a_03__another_workspaces_template_lower_id_404(db, s):
    """WTSV-A-03 — another workspace's template (lower id): 404 `Work order template not found`.
    Rules: `add_item` R2; TC3"""
    z = mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id)
    mk_tpl(db, s)
    commit_point(db)
    before = written(db)
    z_id = z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, tpl_id=z_id, item_in=WorkOrderTemplateItemCreate(item_id=s.I1.id), workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Work order template not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert written(db) == before


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.update_item
# --------------------------------------------------------------------------- #

# [claude] WTSV-I-01
def test_wtsv_i_01__the_changed_line_is_committed_quantity_rounds_half_up(db, s):
    """WTSV-I-01 — the changed line is committed; quantity rounds half up in the column.
    Rules: `update_item` R1; TC1, TC2"""
    t = mk_tpl(db, s)
    line = mk_line(db, s, t)
    commit_point(db)
    l_id = line.id
    result = svc.update_item(db, item_id=l_id, item_in=WorkOrderTemplateItemUpdate(quantity=Decimal("2.125"),
                                                                                   notes="Check seal"),
                             workspace_id=s.W1.id)
    # Then 1
    for col in ("quantity", "notes"):
        assert col not in unloaded(result)
    # Then 2
    assert result.id == l_id
    assert result.quantity == Decimal("2.13")
    assert result.notes == "Check seal"
    # Then 3
    db.rollback()
    row = reread(db, WorkOrderTemplateItem, l_id)
    assert row.quantity == Decimal("2.13")
    assert row.notes == "Check seal"


# [claude] WTSV-I-02
def test_wtsv_i_02__a_line_of_another_workspace_higher_id_404(db, s):
    """WTSV-I-02 — a line of another workspace (higher id): the 404 passes unchanged.
    Rules: `update_item` R2; TC3"""
    t = mk_tpl(db, s)
    mk_line(db, s, t)
    z = mk_tpl(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT2.id)
    zl = mk_line(db, s, z, workspace_id=s.W2.id)
    commit_point(db)
    before_zl = snap_before(db, zl)
    zl_id = zl.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_item(db, item_id=zl_id, item_in=WorkOrderTemplateItemUpdate(quantity=Decimal(5)),
                        workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert snap(db, WorkOrderTemplateItem, zl_id) == before_zl


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.remove_item
# --------------------------------------------------------------------------- #

# [claude] WTSV-R-01
def test_wtsv_r_01__the_delete_is_committed_the_returned_line_stays_readable(db, s):
    """WTSV-R-01 — the delete is committed; the returned line stays readable; the other line stays.
    Rules: `remove_item` R1, Returns; TC1"""
    t = mk_tpl(db, s)
    l1 = mk_line(db, s, t)
    l2 = mk_line(db, s, t, item_id=s.I2.id)
    commit_point(db)
    l1_id, l2_id = l1.id, l2.id
    result = svc.remove_item(db, item_id=l1_id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == l1_id
    assert result.quantity == Decimal("2.00")
    # Then 2
    db.rollback()
    assert count(db, WorkOrderTemplateItem, id=l1_id) == 0
    # Then 3
    assert reread(db, WorkOrderTemplateItem, l2_id).item_id == s.I2.id


# [claude] WTSV-R-02
def test_wtsv_r_02__a_line_of_another_workspace_lower_id_404_nothing_deleted(db, s):
    """WTSV-R-02 — a line of another workspace (lower id): 404, nothing deleted.
    Rules: `remove_item` R2; TC3"""
    z = mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id)
    zl = mk_line(db, s, z, workspace_id=s.W0.id)
    mk_tpl(db, s)
    commit_point(db)
    before = written(db)
    zl_id = zl.id
    x_id = extra_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=zl_id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_rows(db, x_id) == 0
    # Then 5
    assert written(db) == before


# [claude] WTSV-R-03
def test_wtsv_r_03__a_failing_commit_rolled_back_the_line_is_still_there(db, s):
    """WTSV-R-03 — a failing commit: rolled back, re-raised, the line is still there.
    Rules: `remove_item` R2; TC4"""
    t = mk_tpl(db, s)
    line = mk_line(db, s, t)
    commit_point(db)
    l_id = line.id
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.remove_item(db, item_id=l_id, workspace_id=s.W1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count(db, WorkOrderTemplateItem, id=l_id) == 1


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.get_items
# --------------------------------------------------------------------------- #

# [claude] WTSV-N-01
def test_wtsv_n_01__the_templates_lines_are_returned_no_commit_no_rollback(db, s):
    """WTSV-N-01 — the template's lines are returned; the read neither commits nor rolls back.
    Rules: `get_items` R1, R2; TC6"""
    t = mk_tpl(db, s)
    a = mk_line(db, s, t)
    b = mk_line(db, s, t, item_id=s.I2.id)
    commit_point(db)
    x_id = extra_x(db, s)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_items(db, tpl_id=t.id, workspace_id=s.W1.id)
    # Then 1
    assert {r.id for r in result} == {a.id, b.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_rows(db, x_id) == 1


# [claude] WTSV-N-02
def test_wtsv_n_02__another_workspaces_template_gives_an_empty_list(db, s):
    """WTSV-N-02 — another workspace's template gives an empty list.
    Rules: `get_items` R1"""
    mk_tpl(db, s)
    z = mk_tpl(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT2.id)
    mk_line(db, s, z, workspace_id=s.W2.id)
    commit_point(db)
    result = svc.get_items(db, tpl_id=z.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.get_approvers
# --------------------------------------------------------------------------- #

# [claude] WTSV-P-01
def test_wtsv_p_01__the_templates_approvers_are_returned_no_commit_no_rollback(db, s):
    """WTSV-P-01 — the template's approvers are returned; the read neither commits nor rolls back.
    Rules: `get_approvers` R1, R2; TC6"""
    t = mk_tpl(db, s, requires_approval=True)
    mk_approver(db, s, t, s.U2)
    mk_approver(db, s, t, s.U1)
    commit_point(db)
    x_id = extra_x(db, s)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_approvers(db, tpl_id=t.id, workspace_id=s.W1.id)
    # Then 1
    assert {a.user_id for a in result} == {s.U1.id, s.U2.id}
    # Then 2
    assert len(result) == 2
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_rows(db, x_id) == 1


# [claude] WTSV-P-02
def test_wtsv_p_02__another_workspaces_template_gives_an_empty_list(db, s):
    """WTSV-P-02 — another workspace's template gives an empty list.
    Rules: `get_approvers` R1"""
    z = mk_tpl(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id, requires_approval=True)
    db.add(WorkOrderTemplateApprover(workspace_id=s.W0.id, work_order_template_id=z.id, user_id=s.U2.id))
    db.flush()
    mk_tpl(db, s)
    commit_point(db)
    result = svc.get_approvers(db, tpl_id=z.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# WorkOrderTemplateService.generate_drafts
# --------------------------------------------------------------------------- #

# [claude] WTSV-GD-01
def test_wtsv_gd_01__a_due_templates_draft_and_moved_date_are_committed_together(db, s):
    """WTSV-GD-01 — a due template's draft and its moved date are committed together; the draft returned re-read.
    Rules: `generate_drafts` R1, R2; TC1, TC2"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **recurring(p))
    commit_point(db)
    t_id = t.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=s.W1.id,
                                 user_id=s.U1.id)
    # Then 1
    for col in ("planned_date", "work_order_template_id", "machine_id", "created_by"):
        assert col not in unloaded(result[0])
    # Then 2
    assert len(result) == 1
    # Then 3
    assert result[0].work_order_template_id == t_id
    assert result[0].planned_date == D16
    assert result[0].machine_id == p.M1.id
    # Then 4
    assert result[0].workspace_id == s.W1.id
    assert result[0].created_by == s.U1.id
    # Then 5
    db.rollback()
    assert drafts(db, t_id) == 1
    # Then 6
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D23


# [claude] WTSV-GD-02
def test_wtsv_gd_02__nothing_due_an_empty_list_nothing_new_committed(db, s):
    """WTSV-GD-02 — nothing due: an empty list, nothing new committed.
    Rules: `generate_drafts` R2"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **{**recurring(p), "next_generation_date": D17})
    commit_point(db)
    before_t = snap_before(db, t)
    before = written(db)
    t_id = t.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=s.W1.id,
                                 user_id=s.U1.id)
    # Then 1
    assert result == []
    # Then 2
    assert snap(db, WorkOrderTemplate, t_id) == before_t
    # Then 3
    assert written(db) == before


# [claude] WTSV-GD-03
def test_wtsv_gd_03__an_exception_from_the_manager_rolls_back_and_reaches_the_caller(db, s):
    """WTSV-GD-03 — an exception from the manager rolls back the run's date change and reaches the caller as the same object.
    Rules: `generate_drafts` R3; TC3"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **recurring(p))
    commit_point(db)
    before = written(db)
    t_id = t.id
    x_id = extra_x(db, s)
    e = HTTPException(status_code=400, detail="Template is inactive")

    def boom(*a, **k):
        t.next_generation_date = D30
        db.flush()
        raise e

    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.manager, "generate_drafts", side_effect=boom):
            svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=s.W1.id,
                                user_id=s.U1.id)
    # Then 1
    assert exc.value is e
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert x_rows(db, x_id) == 0
    # Then 4
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D16
    # Then 5
    assert written(db) == before


# [claude] WTSV-GD-10
def test_wtsv_gd_10__any_exception_from_the_manager_rolls_the_run_back(db, s):
    """WTSV-GD-10 — any exception from the manager, not only an HTTPException, rolls the run back.
    Rules: `generate_drafts` R3; TC3"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **recurring(p))
    commit_point(db)
    before = written(db)
    t_id = t.id
    x_id = extra_x(db, s)
    e = RuntimeError("boom")

    def boom(*a, **k):
        t.next_generation_date = D30
        db.flush()
        raise e

    with pytest.raises(RuntimeError) as exc:
        with patch.object(svc.manager, "generate_drafts", side_effect=boom):
            svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=s.W1.id,
                                user_id=s.U1.id)
    # Then 1
    assert exc.value is e
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert x_rows(db, x_id) == 0
    # Then 4
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D16
    # Then 5
    assert written(db) == before


# [claude] WTSV-GD-04
@pytest.mark.xfail(strict=True, reason="BUG-2344: One failing template undoes the whole Plan-day run")
def test_wtsv_gd_04__pass_through_bug_2344_one_failing_template_no_longer_undoes_the_other(db, s):
    """WTSV-GD-04 — pass-through BUG-2344: one failing template no longer undoes the other's draft.
    Rules: `generate_drafts` R3 [BUG-2344]"""
    p = mk_plant(db, s)
    m2 = _add(db, Machine(workspace_id=s.W1.id, factory_id=p.F1.id, name="Press 2"))
    t1 = mk_tpl(db, s, **recurring(p))
    t2 = mk_tpl(db, s, **{**recurring(p), "template_name": "Belt check", "default_machine_id": m2.id})
    commit_point(db)
    t1_id, t2_id = t1.id, t2.id
    real = work_order_manager.create_work_order_from_template

    def flaky(*a, **k):
        tpl_id = k["template_id"] if "template_id" in k else a[1]
        if tpl_id == t2_id:
            raise HTTPException(status_code=400, detail="boom")
        return real(*a, **k)

    # Then 1
    with patch.object(work_order_manager, "create_work_order_from_template", side_effect=flaky):
        result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16),
                                     workspace_id=s.W1.id, user_id=s.U1.id)
    assert [w.work_order_template_id for w in result] == [t1_id]
    # Then 2
    db.rollback()
    assert drafts(db, t1_id) == 1
    # Then 3
    assert drafts(db, t2_id) == 0
    # Then 4
    assert reread(db, WorkOrderTemplate, t1_id).next_generation_date == D23
    # Then 5
    assert reread(db, WorkOrderTemplate, t2_id).next_generation_date == D16


# [claude] WTSV-GD-05
def test_wtsv_gd_05__a_failing_re_read_of_a_draft_the_run_stays_committed(db, s):
    """WTSV-GD-05 — a failing re-read of a draft reaches the caller and the run stays committed.
    Rules: `generate_drafts` R4; TC5"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **recurring(p))
    commit_point(db)
    t_id = t.id
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=s.W1.id,
                                user_id=s.U1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert drafts(db, t_id) == 1
    # Then 3
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D23


# [claude] WTSV-GD-06
def test_wtsv_gd_06__factory_section_id_reaches_the_manager(db, s):
    """WTSV-GD-06 — `factory_section_id` reaches the manager: a non-recurring template of the section gets a draft.
    Rules: `generate_drafts` R1"""
    p = mk_plant(db, s)
    s2 = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=p.F1.id, name="Paint"))
    n = mk_tpl(db, s, default_factory_section_id=p.S1.id, default_machine_id=p.M1.id)
    n2 = mk_tpl(db, s, template_name="Belt check", default_factory_section_id=s2.id, default_machine_id=p.M1.id)
    commit_point(db)
    n_id, n2_id = n.id, n2.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16,
                                                                         factory_section_id=p.S1.id),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert [w.work_order_template_id for w in result] == [n_id]
    # Then 2
    assert result[0].planned_date == D16
    assert result[0].machine_id == p.M1.id
    # Then 3
    db.rollback()
    assert drafts(db, n_id) == 1
    # Then 4
    assert drafts(db, n2_id) == 0
    # Then 5
    assert reread(db, WorkOrderTemplate, n_id).next_generation_date is None


# [claude] WTSV-GD-07
def test_wtsv_gd_07__factory_id_reaches_the_manager_another_factory_gets_nothing(db, s):
    """WTSV-GD-07 — `factory_id` reaches the manager: a due template of another factory's section gets nothing.
    Rules: `generate_drafts` R1"""
    p = mk_plant(db, s)
    f2 = _add(db, Factory(workspace_id=s.W1.id, name="Annex", abbreviation="AN"))
    t = mk_tpl(db, s, **recurring(p), default_factory_section_id=p.S1.id)
    commit_point(db)
    before_t = snap_before(db, t)
    before = written(db)
    t_id = t.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16, factory_id=f2.id),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result == []
    # Then 2
    assert snap(db, WorkOrderTemplate, t_id) == before_t
    # Then 3
    assert written(db) == before


# [claude] WTSV-GD-08
@pytest.mark.xfail(strict=True, reason="BUG-2345: A section's \"Plan day\" run makes drafts for recurring templates that are not due")
def test_wtsv_gd_08__pass_through_bug_2345_a_section_run_commits_no_draft_for_not_due(db, s):
    """WTSV-GD-08 — pass-through BUG-2345: a section run commits no draft for a recurring template that is not due.
    Rules: `generate_drafts` R1a [BUG-2345]"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **{**recurring(p), "next_generation_date": D23}, default_factory_section_id=p.S1.id)
    commit_point(db)
    t_id = t.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16,
                                                                         factory_section_id=p.S1.id),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert result == []
    # Then 2
    db.rollback()
    assert drafts(db, t_id) == 0
    # Then 3
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D23


# [claude] WTSV-GD-09
def test_wtsv_gd_09__a_section_run_leaves_a_not_due_templates_next_date(db, s):
    """WTSV-GD-09 — a section run leaves a not-due recurring template's next date where it was.
    Rules: `generate_drafts` R1a"""
    p = mk_plant(db, s)
    t = mk_tpl(db, s, **{**recurring(p), "next_generation_date": D23}, default_factory_section_id=p.S1.id)
    commit_point(db)
    t_id = t.id
    result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16,
                                                                         factory_section_id=p.S1.id),
                                 workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.rollback()
    assert reread(db, WorkOrderTemplate, t_id).next_generation_date == D23
