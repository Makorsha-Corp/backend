"""Unit tests for app/services/order_template_service.py.

Implements tests/unit/services/order_template_service.cases.md (revision 3), one
test per card, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Nothing is patched except the
failing commit / failing refresh wraps and the spies that Conventions name.

How to read these tests:
- Row names of the cards are the lower-case names here (W1 -> `w1`, U2 -> `u2`);
  `# Then N` marks the checks of the card's Then line N.
- "commit point" is `commit_point(db)`; snapshots for "unchanged" and "nothing
  written" are taken right after it. "extra row X" is `extra_x(db, w2)`.
- Bug cards are strict xfails; when the bug is fixed they XPASS, so remove the marker.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`; the cards write `Decimal("0")`)
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.workspace_member import WorkspaceMember
from app.schemas.order_template import (
    OrderTemplateCreate,
    OrderTemplateItemCreate,
    OrderTemplateItemUpdate,
    OrderTemplateUpdate,
)
from app.services.order_template_service import order_template_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton order_template_service"
svc = order_template_service

# Conventions "MISSING", "T0" ... "T3" (naive)
MISSING = 999999999
T0 = datetime(2026, 3, 4, 9, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 3, 4, 10, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 3, 4, 11, 0, 0)  # noqa: DTZ001
T3 = datetime(2026, 3, 4, 12, 0, 0)  # noqa: DTZ001

BUG_1226 = pytest.mark.xfail(strict=True, reason="BUG-1226: Setting a template line's price to 0 leaves the old subtotal")
BUG_2347 = pytest.mark.xfail(
    strict=True, reason="BUG-2347: Any member can make an expense template whose orders skip approval",
)
BUG_2366 = pytest.mark.xfail(strict=True, reason="BUG-2366: Lines of a missing order template answer an empty list")


# --------------------------------------------------------------------------- #
# Conventions -> standing rows: W0 < W1 < W2, then U1, U2
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


# U1 = the acting user
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# U2 = made the Given rows
@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture(autouse=True)
def standing(u2):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "template"
@pytest.fixture
def mk_tpl(db, w1, u2):
    def _mk(**but):
        fields = {
            "workspace_id": w1.id, "template_name": "Rent", "requires_approval": True,
            "auto_approve": False, "created_by": u2.id, "created_at": T0,
        }
        fields.update(but)
        return _add(db, OrderTemplate(**fields))
    return _mk


# Convention "inactive" (after "but")
def inactive(u2):
    return {"is_active": False, "updated_by": u2.id, "updated_at": T0}


# Convention "line n on T"
@pytest.fixture
def mk_line(db, w1):
    def _mk(t, n, **but):
        fields = {
            "workspace_id": w1.id, "order_template_id": t.id, "line_number": n, "description": "Line",
            "quantity": Decimal("2.00"), "unit_price": Decimal("10.00"), "line_subtotal": Decimal("20.00"),
        }
        fields.update(but)
        return _add(db, OrderTemplateItem(**fields))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X": returns X_ID
def extra_x(db, w2):
    x = OrderTemplate(workspace_id=w2.id, template_name="Extra", requires_approval=True, auto_approve=False, created_at=T0)
    db.add(x)
    db.flush()
    return x.id


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id(row)
    db.expire_all()
    return db.get(type(row), row_id)


# Convention "unchanged(X)": every column ...
def snap(db, row):
    table = type(row).__table__
    row_id = _id(row)
    db.expire_all()
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


def count(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar_one()


# Convention "nothing written"
def written(db):
    return (count(db, OrderTemplate), count(db, OrderTemplateItem))


# Conventions "x_gone" / "x_kept": the count of X's id
def x_count(db, x_id):
    return db.scalar(select(func.count()).select_from(OrderTemplate).where(OrderTemplate.id == x_id))


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


def lines_of(db, tpl_id):
    return list(db.execute(
        select(OrderTemplateItem).where(OrderTemplateItem.order_template_id == tpl_id).order_by(OrderTemplateItem.line_number)
    ).scalars())


# =========================================================================== #
# OrderTemplateService.create_template
# =========================================================================== #

# [claude] OTSV-C-01
def test_otsv_c_01__template_with_lines_committed_and_returned_re_read(db, w1, u1):
    """OTSV-C-01 — a template with its lines is committed and returned re-read; the column rounds half up.
    Rules: create_template R1; TC1, TC2"""
    commit_point(db)
    result = svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Desk", quantity=Decimal("1.50"), unit_price=Decimal("0.25")),
        OrderTemplateItemCreate(description="Fee", quantity=Decimal("0.50"), unit_price=Decimal("0.25")),
    ]), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    for col in ("created_at", "template_name", "workspace_id", "created_by", "is_active"):
        assert col not in unloaded(result)
    # Then 2
    assert isinstance(result, OrderTemplate)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.template_name == "Rent"
    assert result.workspace_id == w1.id
    assert result.created_by == u1.id
    assert result.is_active is True
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(OrderTemplate).where(OrderTemplate.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.template_name == "Rent"
    assert row.created_by == u1.id
    # Then 6
    ls = lines_of(db, result_id)
    assert len(ls) == 2
    # Then 7
    assert ls[0].description == "Desk"
    assert ls[0].quantity == Decimal("1.50")
    assert ls[0].unit_price == Decimal("0.25")
    assert ls[0].line_subtotal == Decimal("0.38")
    # Then 8
    assert ls[1].description == "Fee"
    assert ls[1].quantity == Decimal("0.50")
    assert ls[1].unit_price == Decimal("0.25")
    assert ls[1].line_subtotal == Decimal("0.13")


# [claude] OTSV-C-02
def test_otsv_c_02__database_error_rolls_back_and_reaches_the_caller(db, w1, w2):
    """OTSV-C-02 — a database error rolls back, reaches the caller unchanged, and discards other pending changes.
    Rules: create_template R2; TC3"""
    commit_point(db)
    before = written(db)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(IntegrityError):
        svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert x_count(db, x_id) == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert count(db, OrderTemplate, OrderTemplate.workspace_id == w1.id, OrderTemplate.template_name == "Rent") == 0
    # Then 6
    assert usable(db)


# [claude] OTSV-C-03
def test_otsv_c_03__failing_commit_is_rolled_back_and_re_raised(db, w1, u1):
    """OTSV-C-03 — a failing commit is rolled back and re-raised; nothing is saved.
    Rules: create_template R3; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count(db, OrderTemplate, OrderTemplate.workspace_id == w1.id) == 0
    # Then 4
    assert count(db, OrderTemplateItem, OrderTemplateItem.workspace_id == w1.id) == 0


# [claude] OTSV-C-04
def test_otsv_c_04__failing_re_read_leaves_template_and_line_saved(db, w1, u1):
    """OTSV-C-04 — a failing re-read after the commit leaves the template and its line saved.
    Rules: create_template R3, R3a; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[
                OrderTemplateItemCreate(description="Desk", quantity=Decimal("2"), unit_price=Decimal("3.00")),
            ]), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    tpls = list(db.execute(select(OrderTemplate).where(OrderTemplate.workspace_id == w1.id)).scalars())
    assert len(tpls) == 1
    assert tpls[0].template_name == "Rent"
    assert tpls[0].created_by == u1.id
    # Then 3
    items = list(db.execute(select(OrderTemplateItem).where(OrderTemplateItem.workspace_id == w1.id)).scalars())
    assert len(items) == 1
    assert items[0].description == "Desk"
    assert items[0].order_template_id == tpls[0].id
    # Then 4
    assert items[0].line_number == 1
    assert items[0].line_subtotal == Decimal("6.00")


# [claude] OTSV-C-05
def test_otsv_c_05__template_with_no_lines_committed_with_none(db, w1, u1):
    """OTSV-C-05 — a template with no lines is committed with none.
    Rules: create_template R1; TC1"""
    commit_point(db)
    result = svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[]), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id is not None
    result_id = result.id
    # Then 2
    db.rollback()
    assert count(db, OrderTemplate, OrderTemplate.id == result_id) == 1
    # Then 3
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == result_id) == 0


# [claude] OTSV-C-06
@BUG_2347
def test_otsv_c_06__non_owner_template_skipping_approval_refused_403(db, w1, w2, u1, u2):
    """OTSV-C-06 — pass-through BUG-2347: a non-owner's template that skips approval is refused with 403; nothing saved.
    Rules: create_template R2a [BUG-2347]"""
    w1.owner_user_id = u2.id
    db.flush()
    db.add(WorkspaceMember(workspace_id=w1.id, user_id=u1.id, role="member", status="active"))
    db.flush()
    commit_point(db)
    before = written(db)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", requires_approval=False, items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == "Only the workspace owner can skip approval on a template"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert written(db) == before


# =========================================================================== #
# OrderTemplateService.update_template
# =========================================================================== #

# [claude] OTSV-U-01
def test_otsv_u_01__change_committed_and_returned_re_read(db, w1, u1, mk_tpl):
    """OTSV-U-01 — the change is committed and the template returned re-read.
    Rules: update_template R1; TC1, TC2"""
    t = mk_tpl()
    commit_point(db)
    result = svc.update_template(db, tpl_id=t.id, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    for col in ("updated_at", "template_name", "updated_by"):
        assert col not in unloaded(result)
    # Then 2
    assert result.id == t.id
    assert result.template_name == "Lease"
    assert result.updated_by == u1.id
    # Then 3
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, t)
    assert row.template_name == "Lease"
    assert row.updated_by == u1.id


# [claude] OTSV-U-02
def test_otsv_u_02__other_workspaces_id_404_passes_unchanged(db, w1, w2, u1, mk_tpl):
    """OTSV-U-02 — another workspace's id (higher): the manager's 404 passes unchanged, pending changes discarded.
    Rules: update_template R2; TC3"""
    t = mk_tpl()
    z = mk_tpl(workspace_id=w2.id)
    commit_point(db)
    before_z = snap(db, z)
    before_t = snap(db, t)
    before = written(db)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_template(db, tpl_id=z.id, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert x_count(db, x_id) == 0
    # Then 6
    assert snap(db, z) == before_z
    # Then 7
    assert snap(db, t) == before_t
    # Then 8
    assert written(db) == before


# [claude] OTSV-U-03
def test_otsv_u_03__unknown_id_404_nothing_saved(db, w1, u1, mk_tpl):
    """OTSV-U-03 — an unknown id: 404, nothing saved.
    Rules: update_template R2; TC3"""
    t = mk_tpl()
    commit_point(db)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_template(db, tpl_id=MISSING, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template with ID 999999999 not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert snap(db, t) == before_t


# =========================================================================== #
# OrderTemplateService.get_template
# =========================================================================== #

# [claude] OTSV-G-01
def test_otsv_g_01__inactive_template_returned_read_neither_commits_nor_rolls_back(db, w1, w2, u2, mk_tpl):
    """OTSV-G-01 — an inactive template is returned; the read neither commits nor rolls back.
    Rules: get_template R1, R2; TC6"""
    t = mk_tpl(**inactive(u2))
    commit_point(db)
    x_id = extra_x(db, w2)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_template(db, tpl_id=t.id, workspace_id=w1.id)
    # Then 1
    assert result.id == t.id
    assert result.is_active is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1


# [claude] OTSV-G-02
def test_otsv_g_02__other_workspaces_id_lower_404_nothing_rolled_back(db, w0, w1, w2, mk_tpl):
    """OTSV-G-02 — another workspace's id (lower): the 404 passes unchanged and nothing is rolled back.
    Rules: get_template R1, R2; TC6"""
    z = mk_tpl(workspace_id=w0.id)
    mk_tpl()
    commit_point(db)
    x_id = extra_x(db, w2)
    with pytest.raises(HTTPException) as exc:
        with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.get_template(db, tpl_id=z.id, workspace_id=w1.id)
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_count(db, x_id) == 1


# [claude] OTSV-G-03
def test_otsv_g_03__other_workspaces_id_higher_404(db, w1, w2, mk_tpl):
    """OTSV-G-03 — another workspace's id (higher): 404.
    Rules: get_template R1"""
    mk_tpl()
    z = mk_tpl(workspace_id=w2.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_template(db, tpl_id=z.id, workspace_id=w1.id)
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Order template with ID {z.id} not found"


# =========================================================================== #
# OrderTemplateService.list_templates
# =========================================================================== #

# [claude] OTSV-L-01
def test_otsv_l_01__default_lists_active_and_inactive_of_the_workspace(db, w0, w1, w2, u2, mk_tpl):
    """OTSV-L-01 — the default lists active and inactive templates of the workspace only.
    Rules: list_templates R1"""
    mk_tpl(workspace_id=w0.id, created_at=T3)
    a = mk_tpl(created_at=T1)
    b = mk_tpl(**{**inactive(u2), "template_name": "Lease", "created_at": T2})
    mk_tpl(workspace_id=w2.id, created_at=T3)
    commit_point(db)
    result = svc.list_templates(db, workspace_id=w1.id)
    # Then 1
    assert {t.id for t in result} == {a.id, b.id}
    # Then 2
    assert len(result) == 2


# [claude] OTSV-L-02
def test_otsv_l_02__all_five_arguments_reach_the_manager(db, w1, u2, mk_tpl):
    """OTSV-L-02 — all five arguments reach the manager.
    Rules: list_templates R1"""
    a = mk_tpl(**{**inactive(u2), "expense_category": "factory", "created_at": T1})
    mk_tpl(**{**inactive(u2), "template_name": "Lease", "expense_category": "factory", "created_at": T2})
    mk_tpl(template_name="Power", expense_category="factory", created_at=T3)
    mk_tpl(**{**inactive(u2), "template_name": "Misc", "expense_category": "department", "created_at": T3})
    mk_tpl(**{**inactive(u2), "template_name": "Water", "expense_category": "factory", "created_at": T0})
    commit_point(db)
    result = svc.list_templates(db, workspace_id=w1.id, is_active=False, expense_category="factory", skip=1, limit=1)
    # Then 1
    assert [t.id for t in result] == [a.id]


# [claude] OTSV-L-03
def test_otsv_l_03__list_neither_commits_nor_rolls_back(db, w1, w2, mk_tpl):
    """OTSV-L-03 — the list neither commits nor rolls back.
    Rules: list_templates R2; TC6"""
    a = mk_tpl()
    commit_point(db)
    x_id = extra_x(db, w2)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.list_templates(db, workspace_id=w1.id)
    # Then 1
    assert [t.id for t in result] == [a.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1


# [claude] OTSV-L-04
def test_otsv_l_04__no_limit_101_templates_give_newest_100(db, w1, u2):
    """OTSV-L-04 — with no limit, 101 templates give the newest 100.
    Rules: list_templates R1a"""
    rows = [
        OrderTemplate(workspace_id=w1.id, template_name=f"Rent {k}", requires_approval=True, auto_approve=False,
                      created_by=u2.id, created_at=T0 + timedelta(minutes=k))
        for k in range(1, 102)
    ]
    db.add_all(rows)
    db.flush()
    commit_point(db)
    newest = [r.id for r in reversed(rows)]
    result = svc.list_templates(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert [t.id for t in result] == newest[:100]


# =========================================================================== #
# OrderTemplateService.delete_template
# =========================================================================== #

# [claude] OTSV-D-01
def test_otsv_d_01__active_template_deactivated_and_committed(db, w1, u1, mk_tpl, mk_line):
    """OTSV-D-01 — an active template is deactivated and committed; None is returned.
    Rules: delete_template R1, Returns; TC1"""
    t = mk_tpl()
    lx = mk_line(t, 1)
    commit_point(db)
    result = svc.delete_template(db, tpl_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    row = reread(db, t)
    assert row.is_active is False
    assert row.updated_by == u1.id
    # Then 3
    lrow = reread(db, lx)
    assert lrow is not None
    assert lrow.line_number == 1


# [claude] OTSV-D-02
def test_otsv_d_02__already_inactive_template_nothing_new_committed(db, w1, u1, u2, mk_tpl):
    """OTSV-D-02 — an already inactive template: None, nothing new committed.
    Rules: delete_template R1"""
    t = mk_tpl(**inactive(u2))
    commit_point(db)
    before_t = snap(db, t)
    result = svc.delete_template(db, tpl_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t) == before_t
    # Then 3
    row = reread(db, t)
    assert row.updated_by == u2.id
    assert row.updated_at == T0


# [claude] OTSV-D-03
def test_otsv_d_03__other_workspaces_id_lower_404_after_rollback(db, w0, w1, w2, u1, mk_tpl):
    """OTSV-D-03 — another workspace's id (lower): the 404 passes unchanged after a rollback.
    Rules: delete_template R2; TC3"""
    z = mk_tpl(workspace_id=w0.id)
    t = mk_tpl()
    commit_point(db)
    before_z = snap(db, z)
    before_t = snap(db, t)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_template(db, tpl_id=z.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert snap(db, t) == before_t


# [claude] OTSV-D-04
def test_otsv_d_04__failing_commit_template_stays_active(db, w1, u1, mk_tpl):
    """OTSV-D-04 — a failing commit: rolled back, re-raised, the template stays active.
    Rules: delete_template R3; TC4"""
    t = mk_tpl()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_template(db, tpl_id=t.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, t)
    assert row.is_active is True
    assert row.updated_by is None


# =========================================================================== #
# OrderTemplateService.add_item
# =========================================================================== #

# [claude] OTSV-A-01
def test_otsv_a_01__new_line_committed_and_returned_re_read(db, w1, mk_tpl, mk_line):
    """OTSV-A-01 — the new line is committed and returned re-read.
    Rules: add_item R1; TC1, TC2"""
    t = mk_tpl()
    mk_line(t, 1)
    mk_line(t, 2)
    commit_point(db)
    result = svc.add_item(db, tpl_id=t.id, item_in=OrderTemplateItemCreate(description="Water", quantity=Decimal("4"), unit_price=Decimal("2.50")), workspace_id=w1.id)
    # Then 1
    for col in ("line_number", "line_subtotal", "quantity", "unit_price"):
        assert col not in unloaded(result)
    # Then 2
    assert isinstance(result, OrderTemplateItem)
    assert result.order_template_id == t.id
    # Then 3
    assert result.line_number == 3
    assert result.line_subtotal == Decimal("10.00")
    # Then 4
    result_id = result.id
    db.rollback()
    row = db.execute(select(OrderTemplateItem).where(OrderTemplateItem.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.description == "Water"
    assert row.line_number == 3
    assert row.line_subtotal == Decimal("10.00")
    assert row.workspace_id == w1.id


# [claude] OTSV-A-02
def test_otsv_a_02__other_workspaces_template_404_nothing_saved(db, w1, w2, mk_tpl):
    """OTSV-A-02 — another workspace's template (higher id): the 404 passes unchanged; nothing saved.
    Rules: add_item R2; TC3"""
    mk_tpl()
    z = mk_tpl(workspace_id=w2.id)
    commit_point(db)
    before = written(db)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, tpl_id=z.id, item_in=OrderTemplateItemCreate(description="Water"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert written(db) == before


# [claude] OTSV-A-03
def test_otsv_a_03__line_on_inactive_template_committed(db, w1, u2, mk_tpl):
    """OTSV-A-03 — a line on an inactive template is committed.
    Rules: add_item R1; TC1"""
    t = mk_tpl(**inactive(u2))
    t_id = t.id
    commit_point(db)
    result = svc.add_item(db, tpl_id=t_id, item_in=OrderTemplateItemCreate(description="Water"), workspace_id=w1.id)
    # Then 1
    assert result.line_number == 1
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(OrderTemplateItem).where(OrderTemplateItem.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.order_template_id == t_id


# =========================================================================== #
# OrderTemplateService.update_item
# =========================================================================== #

# [claude] OTSV-I-01
def test_otsv_i_01__changed_line_committed_rounded_half_up(db, w1, mk_tpl, mk_line):
    """OTSV-I-01 — the changed line is committed with the manager's subtotal, rounded half up by the column.
    Rules: update_item R1; TC1, TC2"""
    t = mk_tpl()
    lx = mk_line(t, 1)
    commit_point(db)
    result = svc.update_item(db, item_id=lx.id, item_in=OrderTemplateItemUpdate(quantity=Decimal("0.50"), unit_price=Decimal("0.25")), workspace_id=w1.id)
    # Then 1
    for col in ("line_subtotal", "quantity", "unit_price"):
        assert col not in unloaded(result)
    # Then 2
    assert result.id == lx.id
    assert result.line_subtotal == Decimal("0.13")
    # Then 3
    db.rollback()
    row = reread(db, lx)
    assert row.quantity == Decimal("0.50")
    assert row.unit_price == Decimal("0.25")
    assert row.line_subtotal == Decimal("0.13")


# [claude] OTSV-I-02
def test_otsv_i_02__line_of_other_workspace_404(db, w0, w1, w2, mk_tpl, mk_line):
    """OTSV-I-02 — a line of another workspace (lower id): the 404 passes unchanged.
    Rules: update_item R2; TC3"""
    z = mk_tpl(workspace_id=w0.id)
    zl = mk_line(z, 1, workspace_id=w0.id)
    t = mk_tpl()
    lx = mk_line(t, 1)
    commit_point(db)
    before_zl = snap(db, zl)
    before_l = snap(db, lx)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_item(db, item_id=zl.id, item_in=OrderTemplateItemUpdate(quantity=Decimal("5")), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert snap(db, zl) == before_zl
    # Then 6
    assert snap(db, lx) == before_l


# [claude] OTSV-I-03
@BUG_1226
def test_otsv_i_03__price_0_gives_subtotal_0(db, w1, mk_tpl, mk_line):
    """OTSV-I-03 — pass-through BUG-1226: a price of 0 gives a subtotal of 0.
    Rules: update_item R3 [BUG-1226]"""
    t = mk_tpl()
    lx = mk_line(t, 1)
    commit_point(db)
    result = svc.update_item(db, item_id=lx.id, item_in=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert result.unit_price == Decimal("0.00")
    # Then 3
    assert result.line_subtotal == Decimal("0.00")
    # Then 4
    db.rollback()
    assert reread(db, lx).line_subtotal == Decimal("0.00")


# [claude] OTSV-I-04
def test_otsv_i_04__price_0_stored_and_committed(db, w1, mk_tpl, mk_line):
    """OTSV-I-04 — a price of 0 is stored and committed.
    Rules: update_item R1"""
    t = mk_tpl()
    lx = mk_line(t, 1)
    commit_point(db)
    result = svc.update_item(db, item_id=lx.id, item_in=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=w1.id)
    # Then 1
    assert result.id == lx.id
    assert result.unit_price == Decimal("0.00")
    # Then 2
    db.rollback()
    row = reread(db, lx)
    assert row.unit_price == Decimal("0.00")
    assert row.quantity == Decimal("2.00")


# =========================================================================== #
# OrderTemplateService.remove_item
# =========================================================================== #

# [claude] OTSV-R-01
def test_otsv_r_01__delete_committed_returned_line_readable(db, w1, mk_tpl, mk_line):
    """OTSV-R-01 — the delete is committed; the returned line stays readable; the other line keeps its number.
    Rules: remove_item R1, Returns; TC1"""
    t = mk_tpl()
    l1 = mk_line(t, 1)
    l2 = mk_line(t, 2, description="Second")
    l1_id = l1.id
    commit_point(db)
    result = svc.remove_item(db, item_id=l1_id, workspace_id=w1.id)
    # Then 1
    assert result.id == l1_id
    assert result.quantity == Decimal("2.00")
    assert result.description == "Line"
    # Then 2
    db.rollback()
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l1_id) == 0
    # Then 3
    row = reread(db, l2)
    assert row.line_number == 2
    assert row.description == "Second"


# [claude] OTSV-R-02
def test_otsv_r_02__line_of_other_workspace_404_nothing_deleted(db, w1, w2, mk_tpl, mk_line):
    """OTSV-R-02 — a line of another workspace (higher id): the 404 passes unchanged, nothing deleted.
    Rules: remove_item R2; TC3"""
    t = mk_tpl()
    mk_line(t, 1)
    z = mk_tpl(workspace_id=w2.id)
    zl = mk_line(z, 1, workspace_id=w2.id)
    commit_point(db)
    before_zl = snap(db, zl)
    before = written(db)
    x_id = extra_x(db, w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=zl.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 4
    assert x_count(db, x_id) == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, zl) == before_zl


# [claude] OTSV-R-03
def test_otsv_r_03__failing_commit_line_still_there(db, w1, mk_tpl, mk_line):
    """OTSV-R-03 — a failing commit: rolled back, re-raised, the line is still there.
    Rules: remove_item R3; TC4"""
    t = mk_tpl()
    lx = mk_line(t, 1)
    l_id = lx.id
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.remove_item(db, item_id=l_id, workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l_id) == 1


# =========================================================================== #
# OrderTemplateService.get_items
# =========================================================================== #

# [claude] OTSV-GI-01
def test_otsv_gi_01__lines_of_inactive_template_in_line_order(db, w1, w2, u2, mk_tpl, mk_line):
    """OTSV-GI-01 — the lines of an inactive template come back in line order; the read neither commits nor rolls back.
    Rules: get_items R1, R2; TC6"""
    t = mk_tpl(**inactive(u2))
    b = mk_line(t, 2)
    a = mk_line(t, 1, description="First")
    commit_point(db)
    x_id = extra_x(db, w2)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_items(db, tpl_id=t.id, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result] == [a.id, b.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db, x_id) == 1


# [claude] OTSV-GI-02
def test_otsv_gi_02__line_of_other_workspaces_template_not_returned(db, w0, w1, mk_tpl, mk_line):
    """OTSV-GI-02 — a line of another workspace's template is not returned.
    Rules: get_items R1"""
    z = mk_tpl(workspace_id=w0.id)
    mk_line(z, 1, workspace_id=w0.id)
    t = mk_tpl()
    a = mk_line(t, 1)
    commit_point(db)
    result = svc.get_items(db, tpl_id=t.id, workspace_id=w1.id)
    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] OTSV-GI-03
@BUG_2366
def test_otsv_gi_03__other_workspaces_template_answers_404(db, w1, w2, mk_tpl, mk_line):
    """OTSV-GI-03 — pass-through BUG-2366: another workspace's template answers 404, not its lines.
    Rules: get_items R1 [BUG-2366]"""
    t = mk_tpl()
    mk_line(t, 1)
    z = mk_tpl(workspace_id=w2.id)
    mk_line(z, 1, workspace_id=w2.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(db, tpl_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
