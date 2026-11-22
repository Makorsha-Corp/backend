"""Unit tests for app/managers/workspace_manager.py.

Implements tests/unit/managers/workspace_manager.cases.md (revision 2), one test
per card, in card order. Real Postgres session (`db` fixture), rolled back after
each test. The only thing patched in every test is the clock (Conventions,
Externals): `app.managers.workspace_manager.utcnow` and
`app.dao.workspace_invitation.utcnow` both return NOW. WSMG-CW-12 also patches
the slug lookup (Race simulations) and WSMG-CI-04 spies on the token call; both
cards say so.

How to read these tests (they are the reference for the subscription portal):
- A card's row names are the lower-case fixture names here: W1 -> `w1`,
  UA -> `ua`, PL1 -> `pl1`, MO -> `mo` (W1's owner). TAG-based names live on
  `t`: SL -> `t.SL`, EA -> `t.EA`.
- Seats: a workspace's limit is its plan's `max_members` (`set_limit(n)` sets
  W1's). Members count when `status == "active"` (the owner included);
  invitations count when `status == "pending"` and `expires_at > NOW`.
- `# Then N` marks the checks of the card's Then line N. Bug cards are strict
  xfails: they describe the intended behaviour and fail today on the Then line
  their card names; when the bug is fixed they XPASS, so remove the marker.
- The sections "Pending the payment portal (OQ-16)" and "Pending the
  plans/subscriptions design (OQ-17 / BUG-1989)" at the end hold today's
  behaviour for open product decisions; only they change when those are made.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import itertools
import re
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.managers.workspace_manager import workspace_manager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.department import Department
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.factory import Factory
from app.models.item_tag import ItemTag
from app.models.order_workflow import OrderWorkflow
from app.models.project import Project
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.status import Status
from app.models.subscription_plan import SubscriptionPlan
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_assignee import WorkOrderAssignee
from app.models.work_order_completer import WorkOrderCompleter
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_type import WorkOrderType
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_invitation import WorkspaceInvitation
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceCreate
from tests.unit.factories import make_profile, make_subscription_plan, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton workspace_manager"
M = workspace_manager

# Conventions "MISSING", "NOW", "US", "DAY", "T1", "T2" (all datetimes naive UTC)
MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)  # noqa: DTZ001
US = timedelta(microseconds=1)
DAY = timedelta(days=1)
T1 = datetime(2026, 2, 1, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 2, 10, 9, 0, 0)  # noqa: DTZ001

# Expect lines -> markers ("xfail BUG-n" = strict xfail; the reason carries the bug's title from docs/testing/bugs.md)
BUG_1201 = pytest.mark.xfail(strict=True, reason="BUG-1201: A pending approver who left the workspace holds up the order")
BUG_1280 = pytest.mark.xfail(strict=True, reason="BUG-1280: Someone who left the workspace stays on its projects")
# The BUG-1404 cards pass `ip_address` / `user_agent`, which do not exist yet: the When call raises TypeError
BUG_1404 = pytest.mark.xfail(
    strict=True, raises=TypeError, reason="BUG-1404: Workspace audit rows never record IP address or user agent",
)
BUG_1860 = pytest.mark.xfail(strict=True, reason="BUG-1860: An email identifies one account only with its exact capitals")
BUG_1871 = pytest.mark.xfail(
    strict=True, reason="BUG-1871: \"Unlimited\" plan (max_members = -1) cannot send any invitation",
)
# BUG-1872 cards (AM-33, AM-34, AI-14) fail today because the add itself raises the "...limit (-1)..." ValueError
BUG_1872 = pytest.mark.xfail(
    strict=True, raises=ValueError, reason="BUG-1872: \"Unlimited\" plan (max_members = -1) cannot add any member",
)
BUG_1873 = pytest.mark.xfail(strict=True, reason="BUG-1873: Two open invitations to one email take two seats")
BUG_1874 = pytest.mark.xfail(
    strict=True,
    reason="BUG-1874: Accepting one invitation leaves the other invitations to that email pending and counted",
)
BUG_1883 = pytest.mark.xfail(
    strict=True, reason="BUG-1883: A member removed from the workspace stays a planned worker on open work orders",
)
BUG_1980 = pytest.mark.xfail(strict=True, reason="BUG-1980: Workspace names are not trimmed and may be only spaces")
BUG_1981 = pytest.mark.xfail(strict=True, reason="BUG-1981: Cancelling another workspace's invitation says it exists elsewhere")
BUG_1982 = pytest.mark.xfail(strict=True, reason="BUG-1982: A removed member can be invited back but can never accept")
BUG_1983 = pytest.mark.xfail(
    strict=True, reason="BUG-1983: An invitation to a suspended member can never be accepted but holds a seat",
)
BUG_1984 = pytest.mark.xfail(strict=True, reason="BUG-1984: Removing an already removed member succeeds again")
BUG_1985 = pytest.mark.xfail(strict=True, reason="BUG-1985: A new member's row never records who invited them")
BUG_1986 = pytest.mark.xfail(
    strict=True, reason="BUG-1986: A non-owner trying to cancel an invitation learns whether it exists and its state",
)
BUG_1987 = pytest.mark.xfail(strict=True, reason="BUG-1987: Invitation expiry boundary differs from the lists and seat count")
BUG_1990 = pytest.mark.xfail(strict=True, reason="BUG-1990: Any member who is not ground-team can remove any non-owner member")


# AI-28 names BUG-1404 (the call raises TypeError today) but also needs BUG-1874 for its Then 2
BUG_1404_AND_1874 = pytest.mark.xfail(
    strict=True, raises=TypeError,
    reason="BUG-1404: Workspace audit rows never record IP address or user agent; "
    "BUG-1874: Accepting one invitation leaves the other invitations to that email pending and counted "
    "(needed for Then 2)",
)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> TAG-based names and the clock
# --------------------------------------------------------------------------- #

# Conventions "TAG", "SL", "EO", "EA" ... "EE": computed once per test.
# ED and EE belong to no profile.
@pytest.fixture
def t():
    tag = uuid.uuid4().hex[:8]
    return SimpleNamespace(
        TAG=tag,
        SL=f"acme-{tag}",
        EO=f"own.{tag}@acme.com",
        EA=f"ann.{tag}@acme.com",
        EB=f"bob.{tag}@acme.com",
        EC=f"cat.{tag}@acme.com",
        ED=f"dan.{tag}@acme.com",
        EE=f"eve.{tag}@acme.com",
    )


# Convention "Externals": the manager's clock and the invitation DAO's clock both read NOW
@pytest.fixture(autouse=True)
def clock():
    with patch("app.managers.workspace_manager.utcnow", return_value=NOW), \
            patch("app.dao.workspace_invitation.utcnow", return_value=NOW):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #

# 1. PL0, PL1, PL2: plans with max_members 10, not default, active
@pytest.fixture
def pl0(db):
    return make_subscription_plan(db, max_members=10)


@pytest.fixture
def pl1(db, pl0):
    return make_subscription_plan(db, max_members=10)


@pytest.fixture
def pl2(db, pl1):
    return make_subscription_plan(db, max_members=10)


# 2. W0, W1, W2 on PL0, PL1, PL2, so W0.id < W1.id < W2.id
@pytest.fixture
def w0(db, pl0, pl2):
    return make_workspace(db, subscription_plan_id=pl0.id)


@pytest.fixture
def w1(db, pl1, w0):
    return make_workspace(db, subscription_plan_id=pl1.id)


@pytest.fixture
def w2(db, pl2, w1):
    return make_workspace(db, subscription_plan_id=pl2.id)


# 3. UO, UA, UB, UC, so UO.id < UA.id < UB.id < UC.id
@pytest.fixture
def uo(db, t, w2):
    return make_profile(db, email=t.EO, name="Olive Owner")


@pytest.fixture
def ua(db, t, uo):
    return make_profile(db, email=t.EA, name="Ann Lee")


@pytest.fixture
def ub(db, t, ua):
    return make_profile(db, email=t.EB, name="Bob Roy")


@pytest.fixture
def uc(db, t, ub):
    return make_profile(db, email=t.EC, name="Cat Kim")


# 4. MO: W1's owner and, so far, its only member
@pytest.fixture
def mo(db, w1, uo, uc):
    return _add(db, WorkspaceMember(workspace_id=w1.id, user_id=uo.id, role="owner", status="active"))


@pytest.fixture(autouse=True)
def standing_rows(mo):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (inserted directly, never through M; each flushed)
# --------------------------------------------------------------------------- #

# "member(U)": `mk_member(ua)`; the columns after "but" are keywords: `mk_member(ua, status="suspended")`
@pytest.fixture
def mk_member(db, w1):
    def _mk(user, **but):
        fields = {"workspace_id": w1.id, "user_id": user.id, "role": "member", "status": "active"}
        fields.update(but)
        return _add(db, WorkspaceMember(**fields))
    return _mk


# "invitation X to e": `mk_invitation("J", t.ED)` (token f"tok-J-{TAG}"); "but" columns are keywords
@pytest.fixture
def mk_invitation(db, w1, uo, t):
    def _mk(name, email, **but):
        fields = {
            "workspace_id": w1.id, "email": email, "role": "member", "token": f"tok-{name}-{t.TAG}",
            "status": "pending", "expires_at": NOW + DAY, "invited_by_user_id": uo.id,
        }
        fields.update(but)
        return _add(db, WorkspaceInvitation(**fields))
    return _mk


# "limit n": W1's plan gets max_members n
@pytest.fixture
def set_limit(db, pl1):
    def _limit(n):
        pl1.max_members = n
        db.flush()
    return _limit


# Plans for create_workspace_with_owner: `mk_plan("PD")`, `mk_plan("PX")`, `mk_plan("PE")`, `mk_plan("PI")`
@pytest.fixture
def mk_plan(db, t):
    recipes = {
        "PD": {"name": f"free-{t.TAG}", "is_default": True, "is_active": True, "max_members": 3},
        "PX": {"name": f"pro-{t.TAG}", "is_default": False, "is_active": True, "max_members": 10},
        "PE": {"name": f"enterprise-{t.TAG}", "is_default": False, "is_active": True, "max_members": -1},
        "PI": {"name": f"old-{t.TAG}", "is_default": False, "is_active": False, "max_members": 10},
    }

    def _mk(recipe):
        return make_subscription_plan(db, **recipes[recipe])
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (they read; they never hold an expected value)
# --------------------------------------------------------------------------- #

_TABLES = {
    model.__tablename__: model.__table__
    for model in (
        Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceAuditLog, SubscriptionPlan,
        Status, OrderWorkflow, Department, ItemTag, AccountTag,
    )
}
_WRITTEN_TABLES = ("workspaces", "workspace_members", "workspace_invitations", "workspace_audit_logs")
_SEEDED_TABLES = ("statuses", "order_workflows", "departments", "item_tags", "account_tags")


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# "re-read X": expire_all, then SELECT X by id (None when the row is gone)
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns_of(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# "unchanged(X)": `before = snap_before(db, x)` after the last Given line, `assert snap(db, x) == before` after
def snap_before(db, row):
    db.refresh(row)
    return _columns_of(db, row)


def snap(db, row):
    db.expire_all()
    return _columns_of(db, row)


# "unchanged(X) except c": both snapshots without the columns the card leaves out
def without(columns, *names):
    return {k: v for k, v in columns.items() if k not in names}


# "count:" lines: rows of the named table (all workspaces) with the stated equality filters
def count_rows(db, table_name, **filters):
    table = _TABLES[table_name]
    query = select(func.count()).select_from(table)
    for column, value in filters.items():
        query = query.where(table.c[column] == value)
    return db.execute(query).scalar_one()


# "nothing written": `before = written(db)` before the call, `assert written(db) == before` after
def written(db):
    return {name: count_rows(db, name) for name in _WRITTEN_TABLES}


# "nothing seeded": the same for the five seeded tables
def seeded(db):
    return {name: count_rows(db, name) for name in _SEEDED_TABLES}


def _ws_id(ws):
    return ws if isinstance(ws, int) else _id_of(ws)


# "audit(W)" / "audit(W, a)": the W rows ordered by id, a fresh SELECT
def audit(db, ws, action=None):
    db.expire_all()
    query = select(WorkspaceAuditLog).where(WorkspaceAuditLog.workspace_id == _ws_id(ws))
    if action is not None:
        query = query.where(WorkspaceAuditLog.action == action)
    return list(db.execute(query.order_by(WorkspaceAuditLog.id)).scalars())


# "members(W, U)": that user's rows in that workspace, ordered by id
def members(db, ws, user):
    db.expire_all()
    query = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == _ws_id(ws), WorkspaceMember.user_id == _id_of(user),
    )
    return list(db.execute(query.order_by(WorkspaceMember.id)).scalars())


# "invitations(W)": that workspace's invitations, ordered by id; keywords filter by equality
def invitations(db, ws, **filters):
    db.expire_all()
    query = select(WorkspaceInvitation).where(WorkspaceInvitation.workspace_id == _ws_id(ws))
    for column, value in filters.items():
        query = query.where(getattr(WorkspaceInvitation, column) == value)
    return list(db.execute(query.order_by(WorkspaceInvitation.id)).scalars())


# --------------------------------------------------------------------------- #
# WorkspaceManager.create_workspace_with_owner
# (no card here passes a truthy subscription_plan_id: that is OQ-16, section P16)
# --------------------------------------------------------------------------- #

# CW "re-read those rows": the rows of one seeded model in one workspace, a fresh SELECT
def seeded_rows(db, model, workspace_id):
    db.expire_all()
    query = select(model).where(model.workspace_id == workspace_id).order_by(model.id)
    return list(db.execute(query).scalars())


# [claude] WSMG-CW-01
def test_wsmg_cw_01__create_stores_the_workspace_on_the_default_plan_owned_by_the_caller(db, t, ua, mk_plan):
    """WSMG-CW-01 — create stores the workspace on the default plan, owned and created by the caller.
    Rules: `create_workspace_with_owner` R3, R6, Returns"""
    pd = mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL, billing_email="billing@acme.com"),
        owner_user_id=ua.id,
    )

    # Then 1
    assert isinstance(result, Workspace)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Acme Tools"
    assert row.slug == t.SL
    assert row.billing_email == "billing@acme.com"
    # Then 4
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id
    # Then 5
    row = reread(db, result)
    assert row.owner_user_id == ua.id
    assert row.created_by_user_id == ua.id
    # Then 6
    assert count_rows(db, "workspaces", slug=t.SL) == 1


# [claude] WSMG-CW-02
def test_wsmg_cw_02__a_new_workspace_starts_a_14_day_trial_with_the_model_defaults(db, t, ua, mk_plan):
    """WSMG-CW-02 — a new workspace starts a 14-day trial with the model defaults, on the free default plan too.
    Rules: `create_workspace_with_owner` R6"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.trial_ends_at == NOW + timedelta(days=14)
    # Then 3
    row = reread(db, result)
    assert row.subscription_status == "trial"
    assert row.current_members_count == 1
    # Then 4
    row = reread(db, result)
    assert row.subscription_started_at is None
    assert row.subscription_ends_at is None
    assert row.billing_cycle is None
    # Then 5
    row = reread(db, result)
    assert row.stripe_customer_id is None
    assert row.stripe_subscription_id is None
    # Then 6
    row = reread(db, result)
    assert row.billing_email is None
    # Then 7
    row = reread(db, result)
    assert row.current_storage_mb == 0
    assert row.current_orders_this_month == 0
    assert row.current_factories_count == 0
    assert row.current_machines_count == 0
    assert row.current_projects_count == 0
    # Then 8
    row = reread(db, result)
    assert row.last_usage_reset_at is not None


# [claude] WSMG-CW-03
def test_wsmg_cw_03__plan_id_0_means_the_default_plan(db, t, ua, mk_plan):
    """WSMG-CW-03 — plan id 0 means the default plan.
    Rules: `create_workspace_with_owner` R3"""
    mk_plan("PX")
    pd = mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=0,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id
    # Then 3
    rows = audit(db, result)
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"plan": f"free-{t.TAG}"}


# [claude] WSMG-CW-04
def test_wsmg_cw_04__plan_id_none_explicitly_means_the_default_plan_not_another_active(db, t, ua, mk_plan):
    """WSMG-CW-04 — plan id None explicitly means the default plan, not another active plan.
    Rules: `create_workspace_with_owner` R3"""
    pd = mk_plan("PD")
    mk_plan("PX")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=None,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id


# [claude] WSMG-CW-05
def test_wsmg_cw_05__an_inactive_default_plan_is_passed_over_for_the_active_default(db, t, ua, mk_plan):
    """WSMG-CW-05 — an inactive default plan is passed over for the active default.
    Rules: `create_workspace_with_owner` R3"""
    make_subscription_plan(db, name=f"retired-{t.TAG}", is_default=True, is_active=False, max_members=3)
    pd = mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id


# [claude] WSMG-CW-06
def test_wsmg_cw_06__no_active_default_plan_is_refused_and_nothing_is_written(db, t, ua, mk_plan):
    """WSMG-CW-06 — no active default plan is refused and nothing is written.
    Rules: `create_workspace_with_owner` R3; Errors row 2; A3"""
    make_subscription_plan(db, name=f"retired-{t.TAG}", is_default=True, is_active=False, max_members=3)
    mk_plan("PX")
    before = written(db)
    before_seeded = seeded(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)
    # Then 2
    assert str(exc.value) == "No default subscription plan found"
    # Then 3
    assert written(db) == before
    # Then 4
    assert seeded(db) == before_seeded


# [claude] WSMG-CW-07
def test_wsmg_cw_07__an_unknown_plan_id_is_refused_and_nothing_is_written(db, t, ua, mk_plan):
    """WSMG-CW-07 — an unknown plan id is refused and nothing is written.
    Rules: `create_workspace_with_owner` R2; Errors row 1; A3"""
    mk_plan("PD")
    before = written(db)
    before_seeded = seeded(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_workspace_with_owner(
            db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
            subscription_plan_id=MISSING,
        )
    # Then 2
    assert str(exc.value) == "Invalid subscription plan"
    # Then 3
    assert written(db) == before
    # Then 4
    assert seeded(db) == before_seeded


# [claude] WSMG-CW-08
def test_wsmg_cw_08__an_inactive_plan_id_is_refused_and_nothing_is_written(db, t, ua, mk_plan):
    """WSMG-CW-08 — an inactive plan id is refused and nothing is written.
    Rules: `create_workspace_with_owner` R2; Errors row 1; A3"""
    mk_plan("PD")
    pi = mk_plan("PI")
    before = written(db)
    before_seeded = seeded(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_workspace_with_owner(
            db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
            subscription_plan_id=pi.id,
        )
    # Then 2
    assert str(exc.value) == "Invalid subscription plan"
    # Then 3
    assert written(db) == before
    # Then 4
    assert seeded(db) == before_seeded


# [claude] WSMG-CW-09
def test_wsmg_cw_09__a_bad_plan_id_with_a_taken_slug_gives_the_plan_error(db, t, ua, mk_plan):
    """WSMG-CW-09 — a bad plan id with a taken slug gives the plan error.
    Rules: `create_workspace_with_owner` R4"""
    mk_plan("PD")
    make_workspace(db, slug=t.SL)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_workspace_with_owner(
            db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
            subscription_plan_id=MISSING,
        )
    # Then 2
    assert str(exc.value) == "Invalid subscription plan"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CW-10
def test_wsmg_cw_10__a_slug_taken_by_another_owner_s_workspace_is_refused(db, t, ua, ub, mk_plan):
    """WSMG-CW-10 — a slug taken by another owner's workspace is refused and nothing is written.
    Rules: `create_workspace_with_owner` R5; Errors row 3; A3"""
    mk_plan("PD")
    x = make_workspace(db, slug=t.SL, owner_user_id=ub.id)
    before_x = snap_before(db, x)
    before = written(db)
    before_seeded = seeded(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)
    # Then 2
    assert str(exc.value) == f"Workspace slug '{t.SL}' is already taken. Please choose a different name."
    # Then 3
    assert snap(db, x) == before_x
    # Then 4
    assert written(db) == before
    # Then 5
    assert seeded(db) == before_seeded


# [claude] WSMG-CW-11
def test_wsmg_cw_11__a_longer_slug_that_starts_with_the_new_one_does_not_block_it(db, t, ua, mk_plan):
    """WSMG-CW-11 — a longer slug that starts with the new one does not block it.
    Rules: `create_workspace_with_owner` R5"""
    mk_plan("PD")
    make_workspace(db, slug=f"acme-{t.TAG}-tools")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.slug == t.SL


# [claude] WSMG-CW-12
def test_wsmg_cw_12__two_creations_racing_past_the_slug_check_the_unique_index_refuses(
    db, t, ua, mk_plan, monkeypatch,
):
    """WSMG-CW-12 — two creations racing past the slug check: the unique index refuses the second.
    Rules: `create_workspace_with_owner` R5 (race)"""
    mk_plan("PD")
    x = make_workspace(db, slug=t.SL)
    # Race simulation: a concurrent request already passed the slug check
    monkeypatch.setattr(M.workspace_dao, "get_by_slug", lambda *a, **k: None)
    before_x = snap_before(db, x)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_workspace_with_owner(
                db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
            )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "workspaces", slug=t.SL) == 1
    # Then 4
    assert snap(db, x) == before_x


# [claude] WSMG-CW-13
def test_wsmg_cw_13__a_shorter_slug_that_the_new_one_starts_with_does_not_block_it(db, t, ua, mk_plan):
    """WSMG-CW-13 — a shorter slug that the new one starts with does not block it.
    Rules: `create_workspace_with_owner` R5"""
    mk_plan("PD")
    make_workspace(db, slug=t.SL)

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=f"acme-{t.TAG}-tools"), owner_user_id=ua.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.slug == f"acme-{t.TAG}-tools"


# [claude] WSMG-CW-14
def test_wsmg_cw_14__plan_id_and_owner_position_inside_workspace_data_are_ignored(db, t, ua, mk_plan):
    """WSMG-CW-14 — plan id and owner position inside workspace_data are ignored.
    Rules: `create_workspace_with_owner` Inputs (`workspace_data`), R3, R8"""
    pd = mk_plan("PD")
    px = mk_plan("PX")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(
            name="Acme Tools", slug=t.SL, subscription_plan_id=px.id, owner_position="CEO",
        ),
        owner_user_id=ua.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id
    # Then 3
    [member] = members(db, result, ua)
    assert member.position is None


# [claude] WSMG-CW-15
def test_wsmg_cw_15__the_owner_s_timezone_is_copied_into_settings(db, t, mk_plan):
    """WSMG-CW-15 — the owner's timezone is copied into settings.
    Rules: `create_workspace_with_owner` R7"""
    mk_plan("PD")
    z = make_profile(db, email=f"zed.{t.TAG}@acme.com", name="Zed", timezone="Asia/Dhaka")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=z.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.settings == {"timezone": "Asia/Dhaka"}


# [claude] WSMG-CW-16
def test_wsmg_cw_16__an_owner_without_a_timezone_gives_empty_settings(db, t, mk_plan):
    """WSMG-CW-16 — an owner without a timezone gives empty settings.
    Rules: `create_workspace_with_owner` R7"""
    mk_plan("PD")
    z = make_profile(db, email=f"zed.{t.TAG}@acme.com", name="Zed", timezone=None)

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=z.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.settings == {}


# [claude] WSMG-CW-17
def test_wsmg_cw_17__an_owner_with_an_empty_text_timezone_gives_empty_settings(db, t, mk_plan):
    """WSMG-CW-17 — an owner with an empty-text timezone gives empty settings.
    Rules: `create_workspace_with_owner` R7"""
    mk_plan("PD")
    z = make_profile(db, email=f"zed.{t.TAG}@acme.com", name="Zed", timezone="")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=z.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.settings == {}


# [claude] WSMG-CW-18
def test_wsmg_cw_18__the_owner_becomes_the_first_active_member_with_the_given_position(db, t, ua, mk_plan):
    """WSMG-CW-18 — the owner becomes the first, active member with the given position.
    Rules: `create_workspace_with_owner` R8"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, owner_position="Plant Head",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "workspace_members", workspace_id=result.id) == 1
    # Then 3
    [row] = seeded_rows(db, WorkspaceMember, result.id)
    assert row.user_id == ua.id
    assert row.role == "owner"
    assert row.status == "active"
    assert row.position == "Plant Head"
    # Then 4
    row = reread(db, row)
    assert row.joined_at == NOW
    assert row.left_at is None
    assert row.invited_by_user_id is None
    assert row.invited_at is not None


# [claude] WSMG-CW-19
def test_wsmg_cw_19__no_seat_check_is_made_for_the_owner(db, t, ua):
    """WSMG-CW-19 — no seat check is made for the owner.
    Rules: `create_workspace_with_owner` R8"""
    make_subscription_plan(db, name=f"free-{t.TAG}", is_default=True, is_active=True, max_members=-1)

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "workspace_members", workspace_id=result.id, status="active") == 1


# [claude] WSMG-CW-20
def test_wsmg_cw_20__the_new_workspace_gets_its_13_statuses(db, t, ua, mk_plan):
    """WSMG-CW-20 — the new workspace gets its 13 statuses.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "statuses", workspace_id=result.id) == 13
    # Then 3
    rows = seeded_rows(db, Status, result.id)
    assert sorted(s.name for s in rows) == sorted([
        "Pending", "Office Approved", "Budget Approved", "Quotation Requested", "Quotation Received", "Purchased",
        "Received", "Completed", "Cancelled", "Draft", "Planning", "Receiving", "Complete",
    ])


# [claude] WSMG-CW-21
def test_wsmg_cw_21__the_new_workspace_gets_its_purchase_order_workflow(db, t, ua, mk_plan):
    """WSMG-CW-21 — the new workspace gets its purchase order workflow.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "order_workflows", workspace_id=result.id) == 1
    # Then 3
    [row] = seeded_rows(db, OrderWorkflow, result.id)
    assert row.name == "Purchase Order"
    assert row.type == "purchase"
    assert row.description == "Draft → Planning → Receiving → Complete"
    assert row.allowed_reverts_json is None
    # Then 4
    [row] = seeded_rows(db, OrderWorkflow, result.id)
    by_name = {s.name: s for s in seeded_rows(db, Status, result.id)}
    d, p, r, c = by_name["Draft"], by_name["Planning"], by_name["Receiving"], by_name["Complete"]
    assert row.status_sequence == [d.id, p.id, r.id, c.id]


# [claude] WSMG-CW-22
def test_wsmg_cw_22__the_new_workspace_gets_its_5_departments(db, t, ua, mk_plan):
    """WSMG-CW-22 — the new workspace gets its 5 departments.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "departments", workspace_id=result.id) == 5
    # Then 3
    rows = seeded_rows(db, Department, result.id)
    assert sorted(d.name for d in rows) == ["Administration", "Maintenance", "Production", "Quality Control", "Warehouse"]


# [claude] WSMG-CW-23
def test_wsmg_cw_23__the_new_workspace_gets_its_6_system_item_tags(db, t, ua, mk_plan):
    """WSMG-CW-23 — the new workspace gets its 6 system item tags.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "item_tags", workspace_id=result.id) == 6
    # Then 3
    rows = seeded_rows(db, ItemTag, result.id)
    assert sorted(tag.tag_code for tag in rows) == [
        "consumable", "finished_good", "machine_part", "project_item", "raw_material", "tool",
    ]
    # Then 4
    rows = seeded_rows(db, ItemTag, result.id)
    assert all(tag.is_system_tag is True and tag.is_active is True and tag.usage_count == 0 for tag in rows)
    # Then 5
    rows = seeded_rows(db, ItemTag, result.id)
    assert all(tag.created_by == ua.id for tag in rows)


# [claude] WSMG-CW-24
def test_wsmg_cw_24__the_new_workspace_gets_its_5_system_account_tags(db, t, ua, mk_plan):
    """WSMG-CW-24 — the new workspace gets its 5 system account tags.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "account_tags", workspace_id=result.id) == 5
    # Then 3
    rows = seeded_rows(db, AccountTag, result.id)
    assert sorted(tag.tag_code for tag in rows) == ["client", "payroll", "supplier", "utility", "vendor"]
    # Then 4
    rows = seeded_rows(db, AccountTag, result.id)
    assert all(tag.is_system_tag is True and tag.is_active is True and tag.usage_count == 0 for tag in rows)
    # Then 5
    rows = seeded_rows(db, AccountTag, result.id)
    assert all(tag.created_by == ua.id for tag in rows)


# [claude] WSMG-CW-25
def test_wsmg_cw_25__default_data_of_an_earlier_workspace_neither_blocks_the_seed_nor_changes(
    db, t, ua, w0, mk_plan,
):
    """WSMG-CW-25 — default data of an earlier workspace neither blocks the seed nor changes.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")
    s0 = _add(db, Status(workspace_id=w0.id, name="Draft", comment="old"))
    _add(db, Department(workspace_id=w0.id, name="Production"))
    i0 = _add(db, ItemTag(
        workspace_id=w0.id, name="Raw", tag_code="raw_material", is_system_tag=True, is_active=True, usage_count=4,
    ))
    _add(db, AccountTag(
        workspace_id=w0.id, name="Supplier", tag_code="supplier", is_system_tag=True, is_active=True, usage_count=2,
    ))
    o0 = _add(db, OrderWorkflow(workspace_id=w0.id, name="Purchase Order", type="purchase", status_sequence=[s0.id]))
    before_s0 = snap_before(db, s0)
    before_i0 = snap_before(db, i0)
    before_o0 = snap_before(db, o0)

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "statuses", workspace_id=result.id) == 13
    # Then 3
    assert count_rows(db, "departments", workspace_id=result.id) == 5
    # Then 4
    assert count_rows(db, "item_tags", workspace_id=result.id) == 6
    # Then 5
    assert count_rows(db, "account_tags", workspace_id=result.id) == 5
    # Then 6
    assert count_rows(db, "order_workflows", workspace_id=result.id) == 1
    # Then 7
    assert snap(db, s0) == before_s0
    # Then 8
    assert snap(db, i0) == before_i0
    # Then 9
    assert snap(db, o0) == before_o0
    # Then 10
    assert count_rows(db, "statuses", workspace_id=w0.id) == 1


# [claude] WSMG-CW-26
def test_wsmg_cw_26__default_data_of_a_workspace_with_a_higher_id_neither_blocks_nor_changes(db, t, ua, mk_plan):
    """WSMG-CW-26 — default data of a workspace with a higher id neither blocks the seed nor changes.
    Rules: `create_workspace_with_owner` R9"""
    mk_plan("PD")
    wh = make_workspace(db, id=990000000 + int(t.TAG, 16) % 9000000)
    sh = _add(db, Status(workspace_id=wh.id, name="Draft", comment="old"))
    _add(db, Department(workspace_id=wh.id, name="Production"))
    _add(db, ItemTag(
        workspace_id=wh.id, name="Raw", tag_code="raw_material", is_system_tag=True, is_active=True, usage_count=4,
    ))
    ah = _add(db, AccountTag(
        workspace_id=wh.id, name="Supplier", tag_code="supplier", is_system_tag=True, is_active=True, usage_count=2,
    ))
    oh = _add(db, OrderWorkflow(workspace_id=wh.id, name="Purchase Order", type="purchase", status_sequence=[sh.id]))
    before_ah = snap_before(db, ah)
    before_oh = snap_before(db, oh)

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id < wh.id
    # Then 2
    assert count_rows(db, "statuses", workspace_id=result.id) == 13
    # Then 3
    assert count_rows(db, "departments", workspace_id=result.id) == 5
    # Then 4
    assert count_rows(db, "item_tags", workspace_id=result.id) == 6
    # Then 5
    assert count_rows(db, "account_tags", workspace_id=result.id) == 5
    # Then 6
    assert count_rows(db, "order_workflows", workspace_id=result.id) == 1
    # Then 7
    assert snap(db, ah) == before_ah
    # Then 8
    assert snap(db, oh) == before_oh
    # Then 9
    assert count_rows(db, "departments", workspace_id=wh.id) == 1


# [claude] WSMG-CW-27
def test_wsmg_cw_27__one_workspace_created_audit_row_names_the_plan(db, t, ua, mk_plan):
    """WSMG-CW-27 — one workspace_created audit row names the plan.
    Rules: `create_workspace_with_owner` R10; A1"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, result)
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == ua.id
    assert rows[0].action == "workspace_created"
    assert rows[0].metadata_json == {"plan": f"free-{t.TAG}"}
    # Then 4
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None


# [claude] WSMG-CW-28
def test_wsmg_cw_28__an_unknown_owner_fails_at_the_member_insert_the_savepoint_removes_it(db, t, mk_plan):
    """WSMG-CW-28 — an unknown owner fails at the member insert; the savepoint removes the workspace.
    Rules: `create_workspace_with_owner` R11; Errors row 4"""
    mk_plan("PD")
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_workspace_with_owner(
                db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=MISSING,
            )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, "workspaces", slug=t.SL) == 0
    # Then 4
    assert written(db) == before


# [claude] WSMG-CW-29
@BUG_1980
def test_wsmg_cw_29__surrounding_spaces_are_trimmed_from_the_name_inner_spaces_kept(db, t, ua, mk_plan):
    """WSMG-CW-29 — surrounding spaces are trimmed from the name, inner spaces kept.
    Rules: `create_workspace_with_owner` R12 [BUG-1980]"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name=" Acme  Tools ", slug=t.SL), owner_user_id=ua.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Acme  Tools"


# [claude] WSMG-CW-30
@BUG_1980
def test_wsmg_cw_30__a_whitespace_only_name_is_refused_by_the_schema(t):
    """WSMG-CW-30 — a whitespace-only name is refused by the schema.
    Rules: `create_workspace_with_owner` R12 [BUG-1980]"""
    # Then 1
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="   ", slug=t.SL)


# [claude] WSMG-CW-31
def test_wsmg_cw_31__inner_spaces_and_capitals_are_kept_as_typed(db, t, ua, mk_plan):
    """WSMG-CW-31 — inner spaces and capitals are kept as typed.
    Rules: `create_workspace_with_owner` R12"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme  TOOLS", slug=t.SL), owner_user_id=ua.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Acme  TOOLS"


# [claude] WSMG-CW-32
def test_wsmg_cw_32__an_empty_name_is_refused_by_the_schema(t):
    """WSMG-CW-32 — an empty name is refused by the schema.
    Rules: `create_workspace_with_owner` R12"""
    # Then 1
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="", slug=t.SL)


# [claude] WSMG-CW-33
def test_wsmg_cw_33__create_flushes_and_never_commits(db, t, ua, mk_plan):
    """WSMG-CW-33 — create flushes and never commits.
    Rules: `create_workspace_with_owner` Returns; Side effects"""
    mk_plan("PD")

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.create_workspace_with_owner(
            db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
        )

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "workspaces", slug=t.SL) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert count_rows(db, "workspaces", slug=t.SL) == 0


# [claude] WSMG-CW-34
@BUG_1404
def test_wsmg_cw_34__the_audit_row_carries_the_request_s_ip_address_and_user_agent(db, t, ua, mk_plan):
    """WSMG-CW-34 — the audit row carries the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `create_workspace_with_owner` R10"""
    mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id,
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, result)
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# --------------------------------------------------------------------------- #
# WorkspaceManager.add_member_to_workspace
# (seat cards use positive limits only; max_members = 0 is BUG-1989, section P17)
# --------------------------------------------------------------------------- #

# [claude] WSMG-AM-01
def test_wsmg_am_01__the_user_becomes_an_active_member_with_the_given_role_and_position(db, w1, uo, ua):
    """WSMG-AM-01 — the user becomes an active member with the given role and position.
    Rules: `add_member_to_workspace` R7, Returns"""
    result = M.add_member_to_workspace(
        db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id, position="Welder",
    )

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.position == "Welder"
    assert row.status == "active"
    # Then 4
    row = reread(db, result)
    assert row.joined_at == NOW
    assert row.left_at is None
    assert row.invited_at is not None
    # Then 5
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 2


# [claude] WSMG-AM-02
def test_wsmg_am_02__the_role_manager_is_accepted(db, w1, uo, ua):
    """WSMG-AM-02 — the role `manager` is accepted.
    Rules: `add_member_to_workspace` R1"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "manager"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-03
def test_wsmg_am_03__the_role_viewer_is_accepted(db, w1, uo, ua):
    """WSMG-AM-03 — the role `viewer` is accepted.
    Rules: `add_member_to_workspace` R1"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="viewer", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "viewer"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-04
def test_wsmg_am_04__the_role_ground_team_is_accepted(db, w1, uo, ua):
    """WSMG-AM-04 — the role `ground-team` is accepted.
    Rules: `add_member_to_workspace` R1"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="ground-team", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "ground-team"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-05
def test_wsmg_am_05__the_role_owner_is_accepted(db, w1, uo, ua):
    """WSMG-AM-05 — the role `owner` is accepted.
    Rules: `add_member_to_workspace` R1"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="owner", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "owner"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-06
def test_wsmg_am_06__ground_team_manager_is_refused_and_nothing_is_written(db, w1, uo, ua):
    """WSMG-AM-06 — `ground-team-manager` is refused and nothing is written.
    Rules: `add_member_to_workspace` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="ground-team-manager", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-07
def test_wsmg_am_07__finance_is_refused_and_nothing_is_written(db, w1, uo, ua):
    """WSMG-AM-07 — `finance` is refused and nothing is written.
    Rules: `add_member_to_workspace` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="finance", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-08
def test_wsmg_am_08__owner_in_capitals_is_refused_and_nothing_is_written(db, w1, uo, ua):
    """WSMG-AM-08 — `Owner` in capitals is refused and nothing is written.
    Rules: `add_member_to_workspace` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="Owner", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-09
def test_wsmg_am_09__an_empty_role_is_refused_and_nothing_is_written(db, w1, uo, ua):
    """WSMG-AM-09 — an empty role is refused and nothing is written.
    Rules: `add_member_to_workspace` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-10
def test_wsmg_am_10__the_role_is_checked_before_the_workspace_is_looked_up(db, uo, ua):
    """WSMG-AM-10 — the role is checked before the workspace is looked up.
    Rules: `add_member_to_workspace` R1, R3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=MISSING, user_id=ua.id, role="finance", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-11
def test_wsmg_am_11__the_role_is_checked_before_the_existing_row(db, w1, uo, ua, mk_member):
    """WSMG-AM-11 — the role is checked before the existing row.
    Rules: `add_member_to_workspace` R1, R2"""
    a = mk_member(ua)
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="finance", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-12
def test_wsmg_am_12__a_row_with_status_active_is_refused_as_already_a_member(db, w1, uo, ua, mk_member):
    """WSMG-AM-12 — a row with status `"active"` is refused as already a member.
    Rules: `add_member_to_workspace` R2; Errors row 2; A3"""
    a = mk_member(ua)
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User is already a member of this workspace"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-13
def test_wsmg_am_13__a_row_with_status_suspended_is_refused_as_already_a_member(db, w1, uo, ua, mk_member):
    """WSMG-AM-13 — a row with status `"suspended"` is refused as already a member.
    Rules: `add_member_to_workspace` R2; Errors row 2; A3"""
    a = mk_member(ua, status="suspended")
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User is already a member of this workspace"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-14
def test_wsmg_am_14__a_row_with_status_inactive_capitalised_is_refused_as_already_a_member(
    db, w1, uo, ua, mk_member,
):
    """WSMG-AM-14 — a row with status `"Inactive"` is refused as already a member.
    Rules: `add_member_to_workspace` R2; Errors row 2; A3"""
    a = mk_member(ua, status="Inactive")
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User is already a member of this workspace"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-15
def test_wsmg_am_15__a_row_with_status_space_inactive_is_refused_as_already_a_member(db, w1, uo, ua, mk_member):
    """WSMG-AM-15 — a row with status `" inactive"` is refused as already a member.
    Rules: `add_member_to_workspace` R2; Errors row 2; A3"""
    a = mk_member(ua, status=" inactive")
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User is already a member of this workspace"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-16
def test_wsmg_am_16__the_user_s_active_row_in_an_earlier_workspace_does_not_count(db, w0, w1, uo, ua, mk_member):
    """WSMG-AM-16 — the user's active row in an earlier workspace does not count.
    Rules: `add_member_to_workspace` R2"""
    z = mk_member(ua, workspace_id=w0.id)
    before_z = snap_before(db, z)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    assert snap(db, z) == before_z


# [claude] WSMG-AM-17
def test_wsmg_am_17__the_user_s_active_row_in_a_later_workspace_does_not_count(db, w1, w2, uo, ua, mk_member):
    """WSMG-AM-17 — the user's active row in a later workspace does not count.
    Rules: `add_member_to_workspace` R2"""
    z = mk_member(ua, workspace_id=w2.id)
    before_z = snap_before(db, z)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    assert snap(db, z) == before_z


# [claude] WSMG-AM-18
def test_wsmg_am_18__rows_of_other_users_lower_and_higher_ids_do_not_count(db, w1, uo, ua, ub, uc, mk_member):
    """WSMG-AM-18 — rows of other users, one with a lower and one with a higher user id, do not count.
    Rules: `add_member_to_workspace` R2"""
    mk_member(ua)
    mk_member(uc)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ub.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.user_id == ub.id
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ub)) == 1


# [claude] WSMG-AM-19
@BUG_1982
def test_wsmg_am_19__a_removed_inactive_member_is_reactivated_with_the_new_role_and_position(
    db, w1, uo, ua, mk_member,
):
    """WSMG-AM-19 — a removed (inactive) member is reactivated with the new role and position.
    Rules: `add_member_to_workspace` R2a [BUG-1982]"""
    a = mk_member(ua, role="viewer", position="Old", status="inactive", joined_at=T1, left_at=T2)

    result = M.add_member_to_workspace(
        db, workspace_id=w1.id, user_id=ua.id, role="manager", inviter_id=uo.id, position="Lead",
    )

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.status == "active"
    assert row.role == "manager"
    assert row.position == "Lead"
    # Then 3
    row = reread(db, a)
    assert row.joined_at == NOW
    assert row.left_at is None
    # Then 4
    assert len(members(db, w1, ua)) == 1
    # Then 5
    assert len(audit(db, w1, "member_added")) == 1


# [claude] WSMG-AM-20
@BUG_1982
def test_wsmg_am_20__reactivating_a_removed_member_is_refused_when_the_seats_are_full(
    db, w1, uo, ua, ub, mk_member, set_limit,
):
    """WSMG-AM-20 — reactivating a removed member is refused when the seats are full.
    Rules: `add_member_to_workspace` R2a [BUG-1982], R5"""
    set_limit(2)
    mk_member(ub)
    a = mk_member(ua, status="inactive", left_at=T2)
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-21
@BUG_1982
def test_wsmg_am_21__a_removed_member_s_own_inactive_row_does_not_take_a_seat_when_they_come_back(
    db, w1, uo, ua, ub, mk_member, set_limit,
):
    """WSMG-AM-21 — a removed member's own inactive row does not take a seat when they come back.
    Rules: `add_member_to_workspace` R2a [BUG-1982], R5"""
    set_limit(3)
    mk_member(ub)
    a = mk_member(ua, status="inactive", left_at=T2)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.status == "active"
    # Then 3
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 3


# [claude] WSMG-AM-22
def test_wsmg_am_22__an_unknown_workspace_is_refused_and_nothing_is_written(db, uo, ua):
    """WSMG-AM-22 — an unknown workspace is refused and nothing is written.
    Rules: `add_member_to_workspace` R3; Errors row 3; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=MISSING, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace not found"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-23
def test_wsmg_am_23__an_inactive_plan_s_limit_is_still_enforced(db, w1, pl1, uo, ua, ub, mk_member, set_limit):
    """WSMG-AM-23 — an inactive plan's limit is still enforced.
    Rules: `add_member_to_workspace` R4, R5"""
    set_limit(2)
    pl1.is_active = False
    db.flush()
    mk_member(ub)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-24
def test_wsmg_am_24__at_the_limit_3_active_owner_included_the_add_is_refused(
    db, w1, uo, ua, ub, uc, mk_member, set_limit,
):
    """WSMG-AM-24 — at the limit (3 active, owner included) the add is refused.
    Rules: `add_member_to_workspace` R5; Errors row 4; A3"""
    set_limit(3)
    mk_member(ub)
    mk_member(uc)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert len(members(db, w1, ua)) == 0
    # Then 4
    assert written(db) == before


# [claude] WSMG-AM-25
def test_wsmg_am_25__one_seat_below_the_limit_the_add_succeeds(db, w1, uo, ua, ub, mk_member, set_limit):
    """WSMG-AM-25 — one seat below the limit the add succeeds.
    Rules: `add_member_to_workspace` R5"""
    set_limit(3)
    mk_member(ub)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 3


# [claude] WSMG-AM-26
def test_wsmg_am_26__above_the_limit_3_active_on_a_limit_of_2_the_add_is_refused(
    db, w1, uo, ua, ub, uc, mk_member, set_limit,
):
    """WSMG-AM-26 — above the limit (3 active on a limit of 2) the add is refused.
    Rules: `add_member_to_workspace` R5"""
    set_limit(2)
    mk_member(ub)
    mk_member(uc)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-27
def test_wsmg_am_27__the_owner_alone_fills_a_limit_of_1(db, w1, uo, ua, set_limit):
    """WSMG-AM-27 — the owner alone fills a limit of 1.
    Rules: `add_member_to_workspace` R5"""
    set_limit(1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-AM-28
def test_wsmg_am_28__pending_invitations_do_not_take_a_seat_when_adding(
    db, t, w1, uo, ua, ub, mk_member, mk_invitation, set_limit,
):
    """WSMG-AM-28 — pending invitations do not take a seat when adding.
    Rules: `add_member_to_workspace` R5"""
    set_limit(3)
    mk_member(ub)
    mk_invitation("J", t.ED)
    mk_invitation("K", t.EE)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-29
def test_wsmg_am_29__a_suspended_member_does_not_take_a_seat(db, w1, uo, ua, ub, uc, mk_member, set_limit):
    """WSMG-AM-29 — a suspended member does not take a seat.
    Rules: `add_member_to_workspace` R5"""
    set_limit(3)
    mk_member(ub)
    mk_member(uc, status="suspended")

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-30
def test_wsmg_am_30__a_removed_inactive_member_does_not_take_a_seat(db, w1, uo, ua, ub, uc, mk_member, set_limit):
    """WSMG-AM-30 — a removed (inactive) member does not take a seat.
    Rules: `add_member_to_workspace` R5"""
    set_limit(3)
    mk_member(ub)
    mk_member(uc, status="inactive", left_at=T2)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-31
def test_wsmg_am_31__active_members_of_an_earlier_workspace_do_not_take_w1_s_seats(
    db, w0, w1, uo, ua, ub, uc, mk_member, set_limit,
):
    """WSMG-AM-31 — active members of an earlier workspace do not take W1's seats.
    Rules: `add_member_to_workspace` R5"""
    set_limit(2)
    mk_member(ub, workspace_id=w0.id)
    mk_member(uc, workspace_id=w0.id)
    mk_member(ua, workspace_id=w0.id)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-32
def test_wsmg_am_32__active_members_of_a_later_workspace_do_not_take_w1_s_seats(
    db, w1, w2, uo, ua, ub, uc, mk_member, set_limit,
):
    """WSMG-AM-32 — active members of a later workspace do not take W1's seats.
    Rules: `add_member_to_workspace` R5"""
    set_limit(2)
    mk_member(ub, workspace_id=w2.id)
    mk_member(uc, workspace_id=w2.id)
    mk_member(ua, workspace_id=w2.id)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-33
@BUG_1872
def test_wsmg_am_33__a_limit_of_minus_1_means_no_limit(db, w1, uo, ua, ub, uc, mk_member, set_limit):
    """WSMG-AM-33 — a limit of -1 means no limit.
    Rules: `add_member_to_workspace` R5a [BUG-1872]"""
    set_limit(-1)
    mk_member(ub)
    mk_member(uc)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-34
@BUG_1872
def test_wsmg_am_34__a_limit_of_minus_5_means_no_limit(db, w1, uo, ua, ub, mk_member, set_limit):
    """WSMG-AM-34 — a limit of -5 means no limit.
    Rules: `add_member_to_workspace` R5a [BUG-1872]"""
    set_limit(-5)
    mk_member(ub)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.role == "member"
    assert row.status == "active"
    # Then 3
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AM-35
@BUG_1985
def test_wsmg_am_35__the_new_row_records_who_invited_the_member(db, w1, uo, ua):
    """WSMG-AM-35 — the new row records who invited the member.
    Rules: `add_member_to_workspace` R8 [BUG-1985]"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.invited_by_user_id == uo.id


# [claude] WSMG-AM-36
def test_wsmg_am_36__with_no_inviter_the_row_and_the_audit_row_carry_no_actor(db, w1, ua):
    """WSMG-AM-36 — with no inviter the row and the audit row carry no actor.
    Rules: `add_member_to_workspace` R8, R9"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.invited_by_user_id is None
    # Then 3
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id is None
    assert rows[0].action == "member_added"


# [claude] WSMG-AM-37
def test_wsmg_am_37__one_member_added_audit_row_names_the_new_member_and_role(db, w0, w1, uo, ua):
    """WSMG-AM-37 — one member_added audit row names the new member and role.
    Rules: `add_member_to_workspace` R9; A1"""
    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="viewer", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == uo.id
    assert rows[0].action == "member_added"
    assert rows[0].metadata_json == {"new_member_id": ua.id, "role": "viewer"}
    # Then 4
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None
    # Then 5
    assert len(audit(db, w0)) == 0


# [claude] WSMG-AM-38
def test_wsmg_am_38__an_unknown_user_fails_the_insert_with_integrityerror(db, w1, uo):
    """WSMG-AM-38 — an unknown user fails the insert with IntegrityError.
    Rules: `add_member_to_workspace` R10"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.add_member_to_workspace(db, workspace_id=w1.id, user_id=MISSING, role="member", inviter_id=uo.id)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, "workspace_members", workspace_id=w1.id) == 1


# [claude] WSMG-AM-39
def test_wsmg_am_39__add_flushes_and_never_commits(db, w1, uo, ua):
    """WSMG-AM-39 — add flushes and never commits.
    Rules: `add_member_to_workspace` Returns; Side effects"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(members(db, w1, ua)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert len(members(db, w1, ua)) == 0


# [claude] WSMG-AM-40
@BUG_1404
def test_wsmg_am_40__the_audit_row_carries_the_request_s_ip_address_and_user_agent(db, w1, uo, ua):
    """WSMG-AM-40 — the audit row carries the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `add_member_to_workspace` R9"""
    result = M.add_member_to_workspace(
        db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id,
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# --------------------------------------------------------------------------- #
# WorkspaceManager.remove_member_from_workspace
# Role pairs first (RM-01 … RM-47): one card per remover role x target role.
# The remover's own row (R, user UB) carries the role passed in; the manager
# reads only `remover_role`. Who may remove whom (BUG-1990, owner's answer):
#   owner                         -> any non-owner member
#   ground-team-manager, manager  -> ground-team members only
#   anyone else                   -> nobody ("You do not have permission ...")
# --------------------------------------------------------------------------- #

# [claude] WSMG-RM-01, WSMG-RM-02, WSMG-RM-03, WSMG-RM-04, WSMG-RM-05, WSMG-RM-06
@pytest.mark.parametrize("target_role", [
    pytest.param("manager", id="WSMG-RM-01"),
    pytest.param("member", id="WSMG-RM-02"),
    pytest.param("viewer", id="WSMG-RM-03"),
    pytest.param("ground-team", id="WSMG-RM-04"),
    pytest.param("ground-team-manager", id="WSMG-RM-05"),
    pytest.param("finance", id="WSMG-RM-06"),
])
def test_wsmg_rm_01_to_06__the_owner_removes_a_target_of_any_non_owner_role(
    db, w1, uo, ua, mk_member, target_role,
):
    """WSMG-RM-01 … RM-06 — the owner removes a target of role manager, member, viewer, ground-team,
    ground-team-manager or finance. Rules: `remove_member_from_workspace` R5a, R6, R7"""
    t_row = mk_member(ua, role=target_role)

    result = M.remove_member_from_workspace(
        db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner",
    )

    # Then 1
    row = reread(db, t_row)
    assert row.status == "inactive"
    assert row.left_at == NOW
    # Then 2
    row = reread(db, t_row)
    assert row.role == target_role
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 5
    assert rows[0].user_id == uo.id
    assert rows[0].action == "member_removed"
    assert rows[0].metadata_json == {"removed_member_id": ua.id}
    # Then 6
    assert result is None


# [claude] WSMG-RM-07, WSMG-RM-13
@pytest.mark.parametrize("remover_role", [
    pytest.param("ground-team-manager", id="WSMG-RM-07"),
    pytest.param("manager", id="WSMG-RM-13"),
])
def test_wsmg_rm_07_13__a_ground_team_manager_or_manager_removes_a_ground_team_target(
    db, w1, ua, ub, mk_member, remover_role,
):
    """WSMG-RM-07, RM-13 — a `ground-team-manager` (R4) or a `manager` (R4a) removes a target of role `ground-team`.
    Rules: `remove_member_from_workspace` R4, R4a, R6, R7"""
    t_row = mk_member(ua, role="ground-team")
    mk_member(ub, role=remover_role)

    result = M.remove_member_from_workspace(
        db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role=remover_role,
    )

    # Then 1
    row = reread(db, t_row)
    assert row.status == "inactive"
    assert row.left_at == NOW
    # Then 2
    row = reread(db, t_row)
    assert row.role == "ground-team"
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 5
    assert rows[0].user_id == ub.id
    assert rows[0].action == "member_removed"
    assert rows[0].metadata_json == {"removed_member_id": ua.id}
    # Then 6
    assert result is None


# [claude] WSMG-RM-08, WSMG-RM-09, WSMG-RM-10, WSMG-RM-11, WSMG-RM-12,
#          WSMG-RM-14, WSMG-RM-15, WSMG-RM-16, WSMG-RM-17, WSMG-RM-18
@pytest.mark.parametrize(("remover_role", "target_role"), [
    pytest.param("ground-team-manager", "manager", id="WSMG-RM-08"),
    pytest.param("ground-team-manager", "member", id="WSMG-RM-09"),
    pytest.param("ground-team-manager", "viewer", id="WSMG-RM-10"),
    pytest.param("ground-team-manager", "ground-team-manager", id="WSMG-RM-11"),
    pytest.param("ground-team-manager", "finance", id="WSMG-RM-12"),
    pytest.param("manager", "manager", id="WSMG-RM-14", marks=BUG_1990),
    pytest.param("manager", "member", id="WSMG-RM-15", marks=BUG_1990),
    pytest.param("manager", "viewer", id="WSMG-RM-16", marks=BUG_1990),
    pytest.param("manager", "ground-team-manager", id="WSMG-RM-17", marks=BUG_1990),
    pytest.param("manager", "finance", id="WSMG-RM-18", marks=BUG_1990),
])
def test_wsmg_rm_08_to_18__a_manager_may_remove_ground_team_only(
    db, w1, ua, ub, mk_member, remover_role, target_role,
):
    """WSMG-RM-08 … RM-12, RM-14 … RM-18 — a `ground-team-manager` (R4) or a `manager` (R4b, BUG-1990) may not
    remove a target that is not `ground-team`. Rules: `remove_member_from_workspace` R4, R4b [BUG-1990]"""
    t_row = mk_member(ua, role=target_role)
    mk_member(ub, role=remover_role)
    before_t = snap_before(db, t_row)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role=remover_role,
        )
    # Then 2
    assert str(exc.value) == "Managers can only remove ground-team members"
    # Then 3
    assert snap(db, t_row) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-19 … WSMG-RM-47 (every ID listed in the parameters below)
@pytest.mark.parametrize(("remover_role", "target_role"), [
    # R3: ground-team never removes (holds today)
    pytest.param("ground-team", "manager", id="WSMG-RM-19"),
    pytest.param("ground-team", "member", id="WSMG-RM-20"),
    pytest.param("ground-team", "viewer", id="WSMG-RM-21"),
    pytest.param("ground-team", "ground-team", id="WSMG-RM-22"),
    pytest.param("ground-team", "ground-team-manager", id="WSMG-RM-23"),
    pytest.param("ground-team", "finance", id="WSMG-RM-24"),
    # R5 [BUG-1990]: member, viewer and finance never remove
    pytest.param("member", "manager", id="WSMG-RM-25", marks=BUG_1990),
    pytest.param("member", "member", id="WSMG-RM-26", marks=BUG_1990),
    pytest.param("member", "viewer", id="WSMG-RM-27", marks=BUG_1990),
    pytest.param("member", "ground-team", id="WSMG-RM-28", marks=BUG_1990),
    pytest.param("member", "ground-team-manager", id="WSMG-RM-29", marks=BUG_1990),
    pytest.param("member", "finance", id="WSMG-RM-30", marks=BUG_1990),
    pytest.param("viewer", "manager", id="WSMG-RM-31", marks=BUG_1990),
    pytest.param("viewer", "member", id="WSMG-RM-32", marks=BUG_1990),
    pytest.param("viewer", "viewer", id="WSMG-RM-33", marks=BUG_1990),
    pytest.param("viewer", "ground-team", id="WSMG-RM-34", marks=BUG_1990),
    pytest.param("viewer", "ground-team-manager", id="WSMG-RM-35", marks=BUG_1990),
    pytest.param("viewer", "finance", id="WSMG-RM-36", marks=BUG_1990),
    pytest.param("finance", "manager", id="WSMG-RM-37", marks=BUG_1990),
    pytest.param("finance", "member", id="WSMG-RM-38", marks=BUG_1990),
    pytest.param("finance", "viewer", id="WSMG-RM-39", marks=BUG_1990),
    pytest.param("finance", "ground-team", id="WSMG-RM-40", marks=BUG_1990),
    pytest.param("finance", "ground-team-manager", id="WSMG-RM-41", marks=BUG_1990),
    pytest.param("finance", "finance", id="WSMG-RM-42", marks=BUG_1990),
    # R5 [BUG-1990]: role names match exactly; any other spelling never removes
    pytest.param("Owner", "member", id="WSMG-RM-43", marks=BUG_1990),
    pytest.param("Manager", "ground-team", id="WSMG-RM-44", marks=BUG_1990),
    pytest.param("ground-team-manager ", "ground-team", id="WSMG-RM-45", marks=BUG_1990),
    pytest.param("", "ground-team", id="WSMG-RM-46", marks=BUG_1990),
    pytest.param("admin", "ground-team", id="WSMG-RM-47", marks=BUG_1990),
])
def test_wsmg_rm_19_to_47__other_roles_may_not_remove_anyone(
    db, w1, ua, ub, mk_member, remover_role, target_role,
):
    """WSMG-RM-19 … RM-47 — `ground-team` (R3), and every role except exactly `owner`, `ground-team-manager`
    and `manager` (R5, BUG-1990), may not remove anyone. Rules: `remove_member_from_workspace` R3, R5 [BUG-1990]"""
    t_row = mk_member(ua, role=target_role)
    mk_member(ub, role=remover_role)
    before_t = snap_before(db, t_row)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role=remover_role,
        )
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, t_row) == before_t
    # Then 4
    assert written(db) == before


# --------------------------------------------------------------------------- #
# Clean-up rows (BUG-1201, BUG-1280, BUG-1883): orders, approvers, projects, assignees
# --------------------------------------------------------------------------- #

# Each order type's approver model, keyed by the order model
_APPROVER_OF = {
    ExpenseOrder: (ExpenseOrderApprover, "expense_order_id"),
    PurchaseOrder: (PurchaseOrderApprover, "purchase_order_id"),
    SalesOrder: (SalesOrderApprover, "sales_order_id"),
    TransferOrder: (TransferOrderApprover, "transfer_order_id"),
    WorkOrder: (WorkOrderApprover, "work_order_id"),
}


class OrderBuilder:
    """Rows for the clean-up cards. Every builder inserts one row and flushes.

    Orders belong to W1 unless `ws=w2` is passed; the keywords after that are
    the card's "but" columns. The parents an order needs (a factory, an
    account, a work order type, a "Draft" status) are built once per workspace,
    on first use.
    """

    def __init__(self, db, w1, uo, tag):
        self.db = db
        self.w1 = w1
        self.uo = uo
        self.tag = tag
        self._n = itertools.count(1)
        self._parents = {}

    def _num(self, prefix):
        return f"{prefix}-{self.tag}-{next(self._n)}"

    def parents(self, ws):
        if ws.id not in self._parents:
            p = SimpleNamespace()
            p.factory = _add(self.db, Factory(workspace_id=ws.id, name=f"Plant {ws.id}", abbreviation="PL"))
            p.account = _add(self.db, Account(workspace_id=ws.id, name=f"Client {ws.id}"))
            p.wo_type = _add(self.db, WorkOrderType(workspace_id=ws.id, name="Repair"))
            p.status = _add(self.db, Status(workspace_id=ws.id, name="Draft", comment="stage"))
            self._parents[ws.id] = p
        return self._parents[ws.id]

    def _mk(self, model, fields, but):
        fields.update(but)
        return _add(self.db, model(**fields))

    def eo(self, ws=None, **but):
        ws = ws or self.w1
        return self._mk(ExpenseOrder, {
            "workspace_id": ws.id, "expense_number": self._num("EO"), "expense_category": "other",
            "subtotal": Decimal("0.00"), "total_amount": Decimal("20.00"), "created_by": self.uo.id,
            "description": "Power bill", "completed_at": None, "voided": False,
        }, but)

    def po(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(PurchaseOrder, {
            "workspace_id": ws.id, "po_number": self._num("PO"), "destination_type": "storage",
            "destination_id": p.factory.id, "subtotal": Decimal("0.00"), "total_amount": Decimal("10.50"),
            "current_status_id": p.status.id, "created_by": self.uo.id, "description": "Steel order",
            "voided": False, "invoice_id": None,
        }, but)

    def so(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(SalesOrder, {
            "workspace_id": ws.id, "sales_order_number": self._num("SO"), "account_id": p.account.id,
            "factory_id": p.factory.id, "total_amount": Decimal("30.00"), "current_status_id": p.status.id,
            "created_by": self.uo.id, "description": "Chairs", "order_completed": False, "invoice_id": None,
        }, but)

    def to(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(TransferOrder, {
            "workspace_id": ws.id, "transfer_number": self._num("TO"),
            "source_location_type": "storage", "source_location_id": p.factory.id,
            "destination_location_type": "storage", "destination_location_id": p.factory.id,
            "current_status_id": p.status.id, "created_by": self.uo.id, "completed_at": None,
        }, but)

    def wo(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(WorkOrder, {
            "workspace_id": ws.id, "work_order_number": self._num("WO"), "title": "Fix press",
            "factory_id": p.factory.id, "work_order_type_id": p.wo_type.id, "created_by": self.uo.id,
            "status": "DRAFT",
        }, but)

    # "an invoice with invoice_status s" (W1)
    def inv(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(AccountInvoice, {
            "workspace_id": ws.id, "account_id": p.account.id, "invoice_number": self._num("INV"),
            "invoice_type": "payable", "invoice_status": "draft", "invoice_amount": Decimal("100.00"),
            "paid_amount": Decimal("0.00"), "payment_status": "unpaid", "allow_payments": True,
            "description": "May rent", "invoice_date": T1.date(),
        }, but)

    # "a <Type>OrderApprover row of U" on that order: approved False unless the card says otherwise
    def approver(self, order, user, **but):
        model, fk = _APPROVER_OF[type(order)]
        fields = {"workspace_id": order.workspace_id, fk: order.id, "user_id": user.id, "approved": False}
        return self._mk(model, fields, but)

    def project(self, ws=None, **but):
        ws = ws or self.w1
        p = self.parents(ws)
        return self._mk(Project, {
            "workspace_id": ws.id, "factory_id": p.factory.id, "name": self._num("Project"), "description": "Main",
        }, but)

    def project_member(self, project, user):
        return _add(self.db, ProjectMember(workspace_id=project.workspace_id, project_id=project.id, user_id=user.id))

    def assignee(self, order, user):
        return _add(self.db, WorkOrderAssignee(workspace_id=order.workspace_id, work_order_id=order.id, user_id=user.id))

    def completer(self, order, user):
        return _add(self.db, WorkOrderCompleter(workspace_id=order.workspace_id, work_order_id=order.id, user_id=user.id))


@pytest.fixture
def mk_order(db, w1, uo, t):
    return OrderBuilder(db, w1, uo, t.TAG)


# "count:" lines on the clean-up tables: a fresh SELECT COUNT with the given conditions
def n_rows(db, model, *conditions):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()


# "that row" of an event count: the rows themselves, ordered by id
def rows_of(db, model, *conditions):
    db.expire_all()
    return list(db.execute(select(model).where(*conditions).order_by(model.id)).scalars())


# [claude] WSMG-RM-48
def test_wsmg_rm_48__the_owner_s_own_row_cannot_be_removed_even_by_the_owner(db, w1, uo, mo):
    """WSMG-RM-48 — the owner's own row cannot be removed, even by the owner.
    Rules: `remove_member_from_workspace` R2; Errors row 2; A3"""
    before_mo = snap_before(db, mo)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=uo.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-49
def test_wsmg_rm_49__a_ground_team_remover_asking_to_remove_the_owner_gets_the_owner_message(
    db, w1, uo, ub, mo, mk_member,
):
    """WSMG-RM-49 — a `ground-team` remover asking to remove the owner gets the owner message first.
    Rules: `remove_member_from_workspace` R2, R3"""
    mk_member(ub, role="ground-team")
    before_mo = snap_before(db, mo)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="ground-team",
        )
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-50
def test_wsmg_rm_50__a_ground_team_manager_remover_asking_to_remove_the_owner_gets_the_owner_message(
    db, w1, uo, ub, mo, mk_member,
):
    """WSMG-RM-50 — a `ground-team-manager` remover asking to remove the owner gets the owner message first.
    Rules: `remove_member_from_workspace` R2, R4"""
    mk_member(ub, role="ground-team-manager")
    before_mo = snap_before(db, mo)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="ground-team-manager",
        )
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-51
def test_wsmg_rm_51__a_member_remover_asking_to_remove_the_owner_gets_the_owner_message_first(
    db, w1, uo, ub, mo, mk_member,
):
    """WSMG-RM-51 — a `member` remover asking to remove the owner gets the owner message first.
    Rules: `remove_member_from_workspace` R2, R5"""
    mk_member(ub, role="member")
    before_mo = snap_before(db, mo)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="member")
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-52
def test_wsmg_rm_52__a_user_with_no_row_in_the_workspace_is_refused(db, w1, uo, ua):
    """WSMG-RM-52 — a user with no row in the workspace is refused.
    Rules: `remove_member_from_workspace` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "User is not a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-RM-53
def test_wsmg_rm_53__the_user_s_row_in_an_earlier_workspace_does_not_count(db, w0, w1, uo, ua, mk_member):
    """WSMG-RM-53 — the user's row in an earlier workspace does not count.
    Rules: `remove_member_from_workspace` R1 (HR-16)"""
    z = mk_member(ua, workspace_id=w0.id)
    before_z = snap_before(db, z)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "User is not a member of this workspace"
    # Then 3
    assert snap(db, z) == before_z
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-54
def test_wsmg_rm_54__the_user_s_row_in_a_later_workspace_does_not_count(db, w1, w2, uo, ua, mk_member):
    """WSMG-RM-54 — the user's row in a later workspace does not count.
    Rules: `remove_member_from_workspace` R1 (HR-16)"""
    z = mk_member(ua, workspace_id=w2.id)
    before_z = snap_before(db, z)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "User is not a member of this workspace"
    # Then 3
    assert snap(db, z) == before_z
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-55
def test_wsmg_rm_55__rows_of_other_users_with_a_lower_and_a_higher_user_id_do_not_count(
    db, w1, uo, ua, ub, uc, mk_member,
):
    """WSMG-RM-55 — rows of other users, with a lower and a higher user id, do not count.
    Rules: `remove_member_from_workspace` R1"""
    a = mk_member(ua)
    c = mk_member(uc)
    before_a = snap_before(db, a)
    before_c = snap_before(db, c)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ub.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "User is not a member of this workspace"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert snap(db, c) == before_c
    # Then 5
    assert written(db) == before


# [claude] WSMG-RM-56
@BUG_1984
def test_wsmg_rm_56__an_already_removed_member_is_refused_and_keeps_their_leaving_date(db, w1, uo, ua, mk_member):
    """WSMG-RM-56 — an already removed (inactive) member is refused and keeps their leaving date.
    Rules: `remove_member_from_workspace` R1a [BUG-1984]; Errors row 1"""
    tm = mk_member(ua, status="inactive", joined_at=T1, left_at=T2)
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")
    # Then 2
    assert str(exc.value) == "User is not a member of this workspace"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-57
def test_wsmg_rm_57__a_suspended_member_can_be_removed(db, w1, uo, ua, mk_member):
    """WSMG-RM-57 — a suspended member can be removed.
    Rules: `remove_member_from_workspace` R1, R1a, R6"""
    tm = mk_member(ua, status="suspended")

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    assert row.left_at == NOW
    # Then 2
    assert len(audit(db, w1)) == 1
    # Then 3
    assert result is None


# [claude] WSMG-RM-58
def test_wsmg_rm_58__removal_keeps_the_row_its_role_position_and_joining_date(db, w1, uo, ua, mo, mk_member):
    """WSMG-RM-58 — removal keeps the row, its role, position and joining date.
    Rules: `remove_member_from_workspace` R6"""
    tm = mk_member(ua, role="viewer", position="Welder", joined_at=T1)
    before_mo = snap_before(db, mo)

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    assert row.left_at == NOW
    # Then 2
    row = reread(db, tm)
    assert row.role == "viewer"
    assert row.position == "Welder"
    assert row.joined_at == T1
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    assert snap(db, mo) == before_mo
    # Then 5
    assert result is None


# [claude] WSMG-RM-59
def test_wsmg_rm_59__the_remover_id_is_not_checked_an_owner_role_passed_by_someone_with_no_row_removes(
    db, w1, ua, uc, mk_member,
):
    """WSMG-RM-59 — the remover id is not checked: an owner role passed by someone with no row still removes.
    Rules: `remove_member_from_workspace` R5a, R7"""
    tm = mk_member(ua)

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uc.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    assert row.left_at == NOW
    # Then 2
    assert len(members(db, w1, uc)) == 0
    # Then 3
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == uc.id
    assert rows[0].action == "member_removed"
    assert rows[0].metadata_json == {"removed_member_id": ua.id}
    # Then 5
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None
    # Then 6
    assert result is None


# [claude] WSMG-RM-60
@BUG_1990
def test_wsmg_rm_60__a_member_cannot_remove_themselves(db, w1, ua, mk_member):
    """WSMG-RM-60 — a member cannot remove themselves.
    Rules: `remove_member_from_workspace` R5 [BUG-1990]"""
    tm = mk_member(ua)
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ua.id, remover_role="member")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-61
@BUG_1990
def test_wsmg_rm_61__owner_of_an_earlier_workspace_member_here_refused(db, w0, w1, ua, ub, mk_member):
    """WSMG-RM-61 — owner of an earlier workspace, member here: refused.
    Rules: `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)"""
    mk_member(ub, workspace_id=w0.id, role="owner")
    mk_member(ub)
    tm = mk_member(ua)
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="member")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-62
@BUG_1990
def test_wsmg_rm_62__owner_of_a_later_workspace_member_here_refused(db, w1, w2, ua, ub, mk_member):
    """WSMG-RM-62 — owner of a later workspace, member here: refused.
    Rules: `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)"""
    mk_member(ub)
    tm = mk_member(ua)
    mk_member(ub, workspace_id=w2.id, role="owner")
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="member")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-63
@BUG_1990
def test_wsmg_rm_63__ground_team_manager_of_an_earlier_workspace_viewer_here_may_not_remove_ground_team(
    db, w0, w1, ua, ub, mk_member,
):
    """WSMG-RM-63 — ground-team-manager of an earlier workspace, viewer here: may not remove ground-team.
    Rules: `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)"""
    mk_member(ub, workspace_id=w0.id, role="ground-team-manager")
    mk_member(ub, role="viewer")
    tm = mk_member(ua, role="ground-team")
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="viewer")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-64
@BUG_1990
def test_wsmg_rm_64__manager_of_a_later_workspace_viewer_here_may_not_remove_ground_team(
    db, w1, w2, ua, ub, mk_member,
):
    """WSMG-RM-64 — manager of a later workspace, viewer here: may not remove ground-team.
    Rules: `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)"""
    mk_member(ub, role="viewer")
    tm = mk_member(ua, role="ground-team")
    mk_member(ub, workspace_id=w2.id, role="manager")
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="viewer")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-65
def test_wsmg_rm_65__owner_of_a_later_workspace_ground_team_here_refused(db, w1, w2, ua, ub, mk_member):
    """WSMG-RM-65 — owner of a later workspace, ground-team here: refused.
    Rules: `remove_member_from_workspace` R3 (grant held in another workspace)"""
    mk_member(ub, role="ground-team")
    tm = mk_member(ua)
    mk_member(ub, workspace_id=w2.id, role="owner")
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="ground-team",
        )
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-66
def test_wsmg_rm_66__owner_of_an_earlier_workspace_ground_team_manager_here_may_not_remove_a_member(
    db, w0, w1, ua, ub, mk_member,
):
    """WSMG-RM-66 — owner of an earlier workspace, ground-team-manager here: may not remove a member.
    Rules: `remove_member_from_workspace` R4 (grant held in another workspace)"""
    mk_member(ub, workspace_id=w0.id, role="owner")
    mk_member(ub, role="ground-team-manager")
    tm = mk_member(ua)
    before_t = snap_before(db, tm)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="ground-team-manager",
        )
    # Then 2
    assert str(exc.value) == "Managers can only remove ground-team members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert written(db) == before


# [claude] WSMG-RM-67
def test_wsmg_rm_67__removal_leaves_invitations_and_the_member_s_other_workspaces_alone(
    db, t, w1, w2, uo, ua, mk_member, mk_invitation,
):
    """WSMG-RM-67 — removal leaves invitations and the member's other workspaces alone.
    Rules: `remove_member_from_workspace` R12, R11"""
    tm = mk_member(ua)
    z = mk_member(ua, workspace_id=w2.id)
    j = mk_invitation("J", t.EA)
    before_z = snap_before(db, z)
    before_j = snap_before(db, j)

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert snap(db, z) == before_z
    # Then 3
    assert snap(db, j) == before_j
    # Then 4
    assert len(audit(db, w2)) == 0
    # Then 5
    assert result is None


# [claude] WSMG-RM-68
def test_wsmg_rm_68__a_refused_removal_touches_no_approver_project_member_or_assignee_row(
    db, w1, ua, ub, mk_member, mk_order,
):
    """WSMG-RM-68 — a refused removal touches no approver, project member or assignee row.
    Rules: `remove_member_from_workspace` R3, R5, R8, R9, R10"""
    tm = mk_member(ua)
    mk_member(ub, role="ground-team")
    wo1 = mk_order.wo(status="DRAFT")
    mk_order.approver(wo1, ua, approved=False)
    mk_order.assignee(wo1, ua)
    pr1 = mk_order.project()
    mk_order.project_member(pr1, ua)
    before_t = snap_before(db, tm)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="ground-team",
        )
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.user_id == ua.id) == 1
    # Then 5
    assert n_rows(db, WorkOrderAssignee, WorkOrderAssignee.user_id == ua.id) == 1
    # Then 6
    assert n_rows(db, ProjectMember, ProjectMember.user_id == ua.id) == 1
    # Then 7
    assert n_rows(db, WorkOrderEvent, WorkOrderEvent.work_order_id == wo1.id) == 0


# [claude] WSMG-RM-69
@BUG_1990
def test_wsmg_rm_69__a_refused_member_remover_touches_no_approver_project_member_or_assignee_row(
    db, w1, ua, ub, mk_member, mk_order,
):
    """WSMG-RM-69 — a refused member remover touches no approver, project member or assignee row.
    Rules: `remove_member_from_workspace` R5 [BUG-1990]"""
    tm = mk_member(ua)
    mk_member(ub)
    wo1 = mk_order.wo(status="DRAFT")
    mk_order.approver(wo1, ua, approved=False)
    mk_order.assignee(wo1, ua)
    pr1 = mk_order.project()
    mk_order.project_member(pr1, ua)
    before_t = snap_before(db, tm)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=ub.id, remover_role="member")
    # Then 2
    assert str(exc.value) == "You do not have permission to remove members"
    # Then 3
    assert snap(db, tm) == before_t
    # Then 4
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.user_id == ua.id) == 1
    # Then 5
    assert n_rows(db, WorkOrderAssignee, WorkOrderAssignee.user_id == ua.id) == 1
    # Then 6
    assert n_rows(db, ProjectMember, ProjectMember.user_id == ua.id) == 1


# [claude] WSMG-RM-70
@BUG_1201
def test_wsmg_rm_70__removal_deletes_pending_approvals_on_open_expense_orders_only_one_event_per_order(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-70 — removal deletes the member's pending approvals on open expense orders only, with one event per order.
    Rules: `remove_member_from_workspace` R8 [BUG-1201]"""
    tm = mk_member(ua)
    oo = mk_order.eo(completed_at=None, voided=False)
    ap_oo = mk_order.approver(oo, ua, approved=False)
    oc1 = mk_order.eo(completed_at=T2, voided=False)
    ap_oc1 = mk_order.approver(oc1, ua, approved=False)
    oc2 = mk_order.eo(completed_at=None, voided=True)
    ap_oc2 = mk_order.approver(oc2, ua, approved=False)
    oa = mk_order.eo(completed_at=None, voided=False)
    ay = mk_order.approver(oa, ua, approved=True, approved_at=T1)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, ExpenseOrderApprover, ExpenseOrderApprover.id == ap_oo.id) == 0
    # Then 3
    events = rows_of(
        db, ExpenseOrderEvent,
        ExpenseOrderEvent.expense_order_id == oo.id, ExpenseOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 4
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 5
    assert n_rows(db, ExpenseOrderApprover, ExpenseOrderApprover.id == ap_oc1.id) == 1
    # Then 6
    assert n_rows(db, ExpenseOrderApprover, ExpenseOrderApprover.id == ap_oc2.id) == 1
    # Then 7
    assert n_rows(db, ExpenseOrderApprover, ExpenseOrderApprover.id == ay.id) == 1
    # Then 8
    assert n_rows(db, ExpenseOrderEvent, ExpenseOrderEvent.expense_order_id.in_([oc1.id, oc2.id, oa.id])) == 0


# [claude] WSMG-RM-71
@BUG_1201
def test_wsmg_rm_71__removal_deletes_pending_approvals_on_open_purchase_orders_only_one_event_per_order(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-71 — removal deletes the member's pending approvals on open purchase orders only, with one event per order.
    Rules: `remove_member_from_workspace` R8 [BUG-1201]"""
    tm = mk_member(ua)
    sp = _add(db, Status(workspace_id=w1.id, name="Planning", comment="stage"))
    sc = _add(db, Status(workspace_id=w1.id, name="Complete", comment="stage"))
    oo = mk_order.po(voided=False, current_status_id=sp.id, invoice_id=None)
    ap_oo = mk_order.approver(oo, ua, approved=False)
    oo2 = mk_order.po(voided=False, current_status_id=sp.id, invoice_id=mk_order.inv(invoice_status="draft").id)
    ap_oo2 = mk_order.approver(oo2, ua, approved=False)
    oc1 = mk_order.po(voided=True, current_status_id=sp.id, invoice_id=None)
    ap_oc1 = mk_order.approver(oc1, ua, approved=False)
    oc2 = mk_order.po(voided=False, current_status_id=sc.id, invoice_id=None)
    ap_oc2 = mk_order.approver(oc2, ua, approved=False)
    oc3 = mk_order.po(voided=False, current_status_id=sp.id, invoice_id=mk_order.inv(invoice_status="locked").id)
    ap_oc3 = mk_order.approver(oc3, ua, approved=False)
    oa = mk_order.po(voided=False, current_status_id=sp.id, invoice_id=None)
    ay = mk_order.approver(oa, ua, approved=True, approved_at=T1)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ap_oo.id) == 0
    # Then 3
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ap_oo2.id) == 0
    # Then 4
    events = rows_of(
        db, PurchaseOrderEvent,
        PurchaseOrderEvent.purchase_order_id == oo.id, PurchaseOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 5
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 6
    events = rows_of(
        db, PurchaseOrderEvent,
        PurchaseOrderEvent.purchase_order_id == oo2.id, PurchaseOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 7
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 8
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ap_oc1.id) == 1
    # Then 9
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ap_oc2.id) == 1
    # Then 10
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ap_oc3.id) == 1
    # Then 11
    assert n_rows(db, PurchaseOrderApprover, PurchaseOrderApprover.id == ay.id) == 1
    # Then 12
    assert n_rows(
        db, PurchaseOrderEvent, PurchaseOrderEvent.purchase_order_id.in_([oc1.id, oc2.id, oc3.id, oa.id]),
    ) == 0


# [claude] WSMG-RM-72
@BUG_1201
def test_wsmg_rm_72__removal_deletes_pending_approvals_on_open_sales_orders_only_one_event_per_order(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-72 — removal deletes the member's pending approvals on open sales orders only, with one event per order.
    Rules: `remove_member_from_workspace` R8 [BUG-1201]"""
    tm = mk_member(ua)
    oo = mk_order.so(order_completed=False, invoice_id=None)
    ap_oo = mk_order.approver(oo, ua, approved=False)
    oo2 = mk_order.so(order_completed=False, invoice_id=mk_order.inv(invoice_status="draft").id)
    ap_oo2 = mk_order.approver(oo2, ua, approved=False)
    oc1 = mk_order.so(order_completed=True, invoice_id=None)
    ap_oc1 = mk_order.approver(oc1, ua, approved=False)
    oc2 = mk_order.so(order_completed=False, invoice_id=mk_order.inv(invoice_status="confirmed").id)
    ap_oc2 = mk_order.approver(oc2, ua, approved=False)
    oc3 = mk_order.so(order_completed=False, invoice_id=mk_order.inv(invoice_status="locked").id)
    ap_oc3 = mk_order.approver(oc3, ua, approved=False)
    oa = mk_order.so(order_completed=False, invoice_id=None)
    ay = mk_order.approver(oa, ua, approved=True, approved_at=T1)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ap_oo.id) == 0
    # Then 3
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ap_oo2.id) == 0
    # Then 4
    events = rows_of(
        db, SalesOrderEvent, SalesOrderEvent.sales_order_id == oo.id, SalesOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 5
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 6
    events = rows_of(
        db, SalesOrderEvent, SalesOrderEvent.sales_order_id == oo2.id, SalesOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 7
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 8
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ap_oc1.id) == 1
    # Then 9
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ap_oc2.id) == 1
    # Then 10
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ap_oc3.id) == 1
    # Then 11
    assert n_rows(db, SalesOrderApprover, SalesOrderApprover.id == ay.id) == 1
    # Then 12
    assert n_rows(db, SalesOrderEvent, SalesOrderEvent.sales_order_id.in_([oc1.id, oc2.id, oc3.id, oa.id])) == 0


# [claude] WSMG-RM-73
@BUG_1201
def test_wsmg_rm_73__removal_deletes_pending_approvals_on_open_transfer_orders_only_one_event_per_order(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-73 — removal deletes the member's pending approvals on open transfer orders only, with one event per order.
    Rules: `remove_member_from_workspace` R8 [BUG-1201]"""
    tm = mk_member(ua)
    oo = mk_order.to(completed_at=None)
    ap_oo = mk_order.approver(oo, ua, approved=False)
    oc1 = mk_order.to(completed_at=T2)
    ap_oc1 = mk_order.approver(oc1, ua, approved=False)
    oa = mk_order.to(completed_at=None)
    ay = mk_order.approver(oa, ua, approved=True, approved_at=T1)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, TransferOrderApprover, TransferOrderApprover.id == ap_oo.id) == 0
    # Then 3
    events = rows_of(
        db, TransferOrderEvent,
        TransferOrderEvent.transfer_order_id == oo.id, TransferOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 4
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 5
    assert n_rows(db, TransferOrderApprover, TransferOrderApprover.id == ap_oc1.id) == 1
    # Then 6
    assert n_rows(db, TransferOrderApprover, TransferOrderApprover.id == ay.id) == 1
    # Then 7
    assert n_rows(db, TransferOrderEvent, TransferOrderEvent.transfer_order_id.in_([oc1.id, oa.id])) == 0


# [claude] WSMG-RM-74
@BUG_1201
def test_wsmg_rm_74__removal_deletes_pending_approvals_on_open_work_orders_only_one_event_per_order(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-74 — removal deletes the member's pending approvals on open work orders only, with one event per order.
    Rules: `remove_member_from_workspace` R8 [BUG-1201]"""
    tm = mk_member(ua)
    oo = mk_order.wo(status="DRAFT")
    ap_oo = mk_order.approver(oo, ua, approved=False)
    oo2 = mk_order.wo(status="IN_PROGRESS")
    ap_oo2 = mk_order.approver(oo2, ua, approved=False)
    oc1 = mk_order.wo(status="COMPLETED")
    ap_oc1 = mk_order.approver(oc1, ua, approved=False)
    oc2 = mk_order.wo(status="VOIDED")
    ap_oc2 = mk_order.approver(oc2, ua, approved=False)
    oa = mk_order.wo(status="DRAFT")
    ay = mk_order.approver(oa, ua, approved=True, approved_at=T1)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.id == ap_oo.id) == 0
    # Then 3
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.id == ap_oo2.id) == 0
    # Then 4
    events = rows_of(
        db, WorkOrderEvent, WorkOrderEvent.work_order_id == oo.id, WorkOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 5
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 6
    events = rows_of(
        db, WorkOrderEvent, WorkOrderEvent.work_order_id == oo2.id, WorkOrderEvent.event_type == "approver_removed",
    )
    assert len(events) == 1
    # Then 7
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as approver"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 8
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.id == ap_oc1.id) == 1
    # Then 9
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.id == ap_oc2.id) == 1
    # Then 10
    assert n_rows(db, WorkOrderApprover, WorkOrderApprover.id == ay.id) == 1
    # Then 11
    assert n_rows(db, WorkOrderEvent, WorkOrderEvent.work_order_id.in_([oc1.id, oc2.id, oa.id])) == 0


# [claude] WSMG-RM-75
def test_wsmg_rm_75__approved_rows_not_open_orders_and_other_workspaces_keep_their_approver_rows(
    db, w1, w2, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-75 — approved rows, not-open orders and other workspaces keep their approver rows today and after.
    Rules: `remove_member_from_workspace` R8, R11"""
    tm = mk_member(ua)
    planning = _add(db, Status(workspace_id=w1.id, name="Planning", comment="stage"))
    # Given 2: not open, approved False
    closed = [
        mk_order.eo(completed_at=T2),
        mk_order.po(voided=True),
        mk_order.so(order_completed=True),
        mk_order.to(completed_at=T2),
        mk_order.wo(status="COMPLETED"),
    ]
    approvers = [mk_order.approver(order, ua, approved=False) for order in closed]
    # Given 3: open, approved True
    open_orders = [
        mk_order.eo(completed_at=None, voided=False),
        mk_order.po(voided=False, invoice_id=None, current_status_id=planning.id),
        mk_order.so(order_completed=False, invoice_id=None),
        mk_order.to(completed_at=None),
        mk_order.wo(status="DRAFT"),
    ]
    approvers += [mk_order.approver(order, ua, approved=True, approved_at=T1) for order in open_orders]
    # Given 4: W2
    mk_member(ua, workspace_id=w2.id)
    w9 = mk_order.wo(ws=w2, status="DRAFT")
    approvers.append(mk_order.approver(w9, ua, approved=False))
    orders = [*closed, *open_orders, w9]

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert len(approvers) == 11
    assert sum(n_rows(db, type(a), type(a).id == a.id) for a in approvers) == 11
    # Then 3
    event_of = {
        ExpenseOrder: (ExpenseOrderEvent, "expense_order_id"),
        PurchaseOrder: (PurchaseOrderEvent, "purchase_order_id"),
        SalesOrder: (SalesOrderEvent, "sales_order_id"),
        TransferOrder: (TransferOrderEvent, "transfer_order_id"),
        WorkOrder: (WorkOrderEvent, "work_order_id"),
    }
    removed_events = 0
    for order in orders:
        model, fk = event_of[type(order)]
        removed_events += n_rows(db, model, getattr(model, fk) == order.id, model.event_type == "approver_removed")
    assert removed_events == 0
    # Then 4
    assert result is None


# [claude] WSMG-RM-76
@BUG_1280
def test_wsmg_rm_76__removal_deletes_the_member_s_project_memberships_in_this_workspace_one_event_per_project(
    db, w1, uo, ua, ub, mk_member, mk_order,
):
    """WSMG-RM-76 — removal deletes the member's project memberships in this workspace, one event per project.
    Rules: `remove_member_from_workspace` R9 [BUG-1280]"""
    tm = mk_member(ua)
    pr1 = mk_order.project()
    mk_order.project_member(pr1, ua)
    pr2 = mk_order.project()
    mk_order.project_member(pr2, ua)
    pr3 = mk_order.project()
    mk_order.project_member(pr3, ub)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, ProjectMember, ProjectMember.user_id == ua.id, ProjectMember.project_id.in_([pr1.id, pr2.id])) == 0
    # Then 3
    events = rows_of(db, ProjectEvent, ProjectEvent.project_id == pr1.id, ProjectEvent.event_type == "member_removed")
    assert len(events) == 1
    # Then 4
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee from the project"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 5
    assert n_rows(db, ProjectEvent, ProjectEvent.project_id == pr2.id, ProjectEvent.event_type == "member_removed") == 1
    # Then 6
    assert n_rows(db, ProjectMember, ProjectMember.user_id == ub.id, ProjectMember.project_id == pr3.id) == 1


# [claude] WSMG-RM-77
def test_wsmg_rm_77__project_memberships_in_another_workspace_stay(db, w1, w2, uo, ua, mk_member, mk_order):
    """WSMG-RM-77 — project memberships in another workspace stay.
    Rules: `remove_member_from_workspace` R9, R11"""
    tm = mk_member(ua)
    mk_member(ua, workspace_id=w2.id)
    pr9 = mk_order.project(ws=w2)
    pm9 = mk_order.project_member(pr9, ua)

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(db, ProjectMember, ProjectMember.id == pm9.id) == 1
    # Then 3
    assert n_rows(db, ProjectEvent, ProjectEvent.project_id == pr9.id) == 0
    # Then 4
    assert result is None


# [claude] WSMG-RM-78
@BUG_1883
def test_wsmg_rm_78__removal_deletes_the_member_s_assignments_on_draft_and_in_progress_work_orders(
    db, w1, uo, ua, ub, mk_member, mk_order,
):
    """WSMG-RM-78 — removal deletes the member's assignments on draft and in-progress work orders, one event per order.
    Rules: `remove_member_from_workspace` R10 [BUG-1883]"""
    tm = mk_member(ua)
    wd = mk_order.wo(status="DRAFT")
    mk_order.assignee(wd, ua)
    wi = mk_order.wo(status="IN_PROGRESS")
    mk_order.assignee(wi, ua)
    mk_order.assignee(wd, ub)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(
        db, WorkOrderAssignee, WorkOrderAssignee.user_id == ua.id, WorkOrderAssignee.work_order_id.in_([wd.id, wi.id]),
    ) == 0
    # Then 3
    events = rows_of(
        db, WorkOrderEvent, WorkOrderEvent.work_order_id == wd.id, WorkOrderEvent.event_type == "assignee_removed",
    )
    assert len(events) == 1
    # Then 4
    assert events[0].workspace_id == w1.id
    assert events[0].performed_by == uo.id
    assert events[0].description == "Removed Ann Lee as assignee"
    assert events[0].metadata_json == {"user_id": ua.id, "user_name": "Ann Lee"}
    # Then 5
    assert n_rows(
        db, WorkOrderEvent, WorkOrderEvent.work_order_id == wi.id, WorkOrderEvent.event_type == "assignee_removed",
    ) == 1
    # Then 6
    assert n_rows(db, WorkOrderAssignee, WorkOrderAssignee.user_id == ub.id, WorkOrderAssignee.work_order_id == wd.id) == 1


# [claude] WSMG-RM-79
@BUG_1883
def test_wsmg_rm_79__a_soft_deleted_draft_work_order_loses_the_member_s_assignment_too(
    db, w1, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-79 — a soft-deleted draft work order loses the member's assignment too.
    Rules: `remove_member_from_workspace` R10 [BUG-1883]"""
    tm = mk_member(ua)
    ws_order = mk_order.wo(status="DRAFT", is_deleted=True)
    mk_order.assignee(ws_order, ua)

    M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(
        db, WorkOrderAssignee, WorkOrderAssignee.user_id == ua.id, WorkOrderAssignee.work_order_id == ws_order.id,
    ) == 0
    # Then 3
    assert n_rows(
        db, WorkOrderEvent, WorkOrderEvent.work_order_id == ws_order.id, WorkOrderEvent.event_type == "assignee_removed",
    ) == 1


# [claude] WSMG-RM-80
def test_wsmg_rm_80__completed_and_voided_work_orders_completers_other_workspaces_and_free_text_stay(
    db, w1, w2, uo, ua, mk_member, mk_order,
):
    """WSMG-RM-80 — completed and voided work orders, completers, other workspaces and the free-text assignee stay.
    Rules: `remove_member_from_workspace` R10, R11"""
    tm = mk_member(ua)
    wc = mk_order.wo(status="COMPLETED")
    mk_order.assignee(wc, ua)
    wv = mk_order.wo(status="VOIDED")
    mk_order.assignee(wv, ua)
    wd = mk_order.wo(status="DRAFT", assigned_to="Ann Lee")
    mk_order.completer(wd, ua)
    mk_member(ua, workspace_id=w2.id)
    w9 = mk_order.wo(ws=w2, status="DRAFT")
    mk_order.assignee(w9, ua)

    result = M.remove_member_from_workspace(db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner")

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert n_rows(
        db, WorkOrderAssignee,
        WorkOrderAssignee.user_id == ua.id, WorkOrderAssignee.work_order_id.in_([wc.id, wv.id, w9.id]),
    ) == 3
    # Then 3
    assert n_rows(
        db, WorkOrderCompleter, WorkOrderCompleter.user_id == ua.id, WorkOrderCompleter.work_order_id == wd.id,
    ) == 1
    # Then 4
    assert reread(db, wd).assigned_to == "Ann Lee"
    # Then 5
    assert n_rows(db, WorkOrderEvent, WorkOrderEvent.work_order_id.in_([wc.id, wv.id, wd.id, w9.id])) == 0
    # Then 6
    assert result is None


# [claude] WSMG-RM-81
def test_wsmg_rm_81__removal_flushes_and_never_commits(db, w1, uo, ua, mk_member):
    """WSMG-RM-81 — removal flushes and never commits.
    Rules: `remove_member_from_workspace` R11; Side effects"""
    tm = mk_member(ua)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner",
        )

    # Then 1
    row = reread(db, tm)
    assert row.status == "inactive"
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    row = reread(db, tm)
    assert row.status == "active"
    assert row.left_at is None
    # Then 4
    assert result is None


# [claude] WSMG-RM-82
@BUG_1404
def test_wsmg_rm_82__the_audit_row_carries_the_request_s_ip_address_and_user_agent(db, w1, uo, ua, mk_member):
    """WSMG-RM-82 — the audit row carries the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `remove_member_from_workspace` R7"""
    mk_member(ua)

    M.remove_member_from_workspace(
        db, workspace_id=w1.id, user_id=ua.id, remover_id=uo.id, remover_role="owner",
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 2
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSMG-RM-83
def test_wsmg_rm_83__a_manager_remover_asking_to_remove_the_owner_gets_the_owner_message(db, w1, uo, ub, mo, mk_member):
    """WSMG-RM-83 — a `manager` remover asking to remove the owner gets the owner message.
    Rules: `remove_member_from_workspace` R2; Errors row 2; A3"""
    r = mk_member(ub, role="manager")
    before_mo = snap_before(db, mo)
    before_r = snap_before(db, r)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="manager",
        )
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert snap(db, r) == before_r
    # Then 5
    assert written(db) == before


# [claude] WSMG-RM-84
def test_wsmg_rm_84__a_viewer_remover_asking_to_remove_the_owner_gets_the_owner_message(db, w1, uo, ub, mo, mk_member):
    """WSMG-RM-84 — a `viewer` remover asking to remove the owner gets the owner message.
    Rules: `remove_member_from_workspace` R2; Errors row 2; A3"""
    r = mk_member(ub, role="viewer")
    before_mo = snap_before(db, mo)
    before_r = snap_before(db, r)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="viewer",
        )
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert snap(db, r) == before_r
    # Then 5
    assert written(db) == before


# [claude] WSMG-RM-85
def test_wsmg_rm_85__a_finance_remover_asking_to_remove_the_owner_gets_the_owner_message(db, w1, uo, ub, mo, mk_member):
    """WSMG-RM-85 — a `finance` remover asking to remove the owner gets the owner message.
    Rules: `remove_member_from_workspace` R2; Errors row 2; A3"""
    r = mk_member(ub, role="finance")
    before_mo = snap_before(db, mo)
    before_r = snap_before(db, r)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.remove_member_from_workspace(
            db, workspace_id=w1.id, user_id=uo.id, remover_id=ub.id, remover_role="finance",
        )
    # Then 2
    assert str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."
    # Then 3
    assert snap(db, mo) == before_mo
    # Then 4
    assert snap(db, r) == before_r
    # Then 5
    assert written(db) == before


# --------------------------------------------------------------------------- #
# WorkspaceManager.create_invitation
# Seats: active members of W1 (the owner MO included) + W1 invitations with
# status exactly "pending" and expires_at > NOW, against W1's plan max_members.
# Seat cards invite EE, which no Given row uses, so BUG-1873 never fires in them.
# (max_members = 0 is OQ-17 / BUG-1989, section P17)
# --------------------------------------------------------------------------- #


# WSMG-CI-04 "spy tk": wraps the real secrets.token_urlsafe and keeps what it returned in `spy_return`
def token_spy():
    real = secrets.token_urlsafe
    spy = Mock()

    def _call(*args, **kwargs):
        spy.spy_return = real(*args, **kwargs)
        return spy.spy_return
    spy.side_effect = _call
    return spy


# [claude] WSMG-CI-01
def test_wsmg_ci_01__the_invitation_is_stored_pending_with_the_inviter_position_and_3_day_expiry(db, t, w1, uo):
    """WSMG-CI-01 — the invitation is stored pending, with the inviter, position and a 3-day expiry.
    Rules: `create_invitation` R10, R12, Returns"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id, position="Driver")

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.role == "member"
    assert row.position == "Driver"
    # Then 4
    row = reread(db, result)
    assert row.invited_by_user_id == uo.id
    assert row.status == "pending"
    assert row.invited_at is not None
    # Then 5
    row = reread(db, result)
    assert row.accepted_at is None
    assert row.accepted_by_user_id is None
    # Then 6
    row = reread(db, result)
    assert row.expires_at == NOW + timedelta(days=3)
    # Then 7
    assert len(invitations(db, w1)) == 1


# [claude] WSMG-CI-02
def test_wsmg_ci_02__the_email_is_stored_lower_cased(db, t, w1, uo):
    """WSMG-CI-02 — the email is stored lower-cased.
    Rules: `create_invitation` R10"""
    result = M.create_invitation(db, workspace_id=w1.id, email=f"Dan.{t.TAG}@Acme.COM", role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.email == f"dan.{t.TAG}@acme.com"


# [claude] WSMG-CI-03
def test_wsmg_ci_03__the_token_is_a_43_character_url_safe_string(db, t, w1, uo):
    """WSMG-CI-03 — the token is a 43-character URL-safe string.
    Rules: `create_invitation` R11"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert len(row.token) == 43
    # Then 3
    row = reread(db, result)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", row.token) is not None


# [claude] WSMG-CI-04
def test_wsmg_ci_04__the_token_comes_from_a_fresh_secrets_token_urlsafe_32_call(db, t, w1, uo, mk_invitation):
    """WSMG-CI-04 — the token comes from a fresh secrets.token_urlsafe(32) call.
    Rules: `create_invitation` R11"""
    tk = token_spy()
    j = mk_invitation("J", t.EE)

    with patch("app.managers.workspace_manager.secrets.token_urlsafe", new=tk):
        result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert tk.call_count == 1
    # Then 3
    assert tk.call_args.args == (32,)
    # Then 4
    row = reread(db, result)
    assert row.token == tk.spy_return
    # Then 5
    row = reread(db, result)
    assert row.token != j.token


# [claude] WSMG-CI-05
def test_wsmg_ci_05__the_role_manager_is_accepted(db, t, w1, uo):
    """WSMG-CI-05 — the role `manager` is accepted.
    Rules: `create_invitation` R1"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="manager", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.role == "manager"


# [claude] WSMG-CI-06
def test_wsmg_ci_06__the_role_viewer_is_accepted(db, t, w1, uo):
    """WSMG-CI-06 — the role `viewer` is accepted.
    Rules: `create_invitation` R1"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="viewer", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.role == "viewer"


# [claude] WSMG-CI-07
def test_wsmg_ci_07__the_role_ground_team_is_accepted(db, t, w1, uo):
    """WSMG-CI-07 — the role `ground-team` is accepted.
    Rules: `create_invitation` R1"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="ground-team", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.role == "ground-team"


# [claude] WSMG-CI-08 … WSMG-CI-12: one refused role each, same setup and checks
@pytest.mark.parametrize("role", [
    pytest.param("owner", id="WSMG-CI-08"),
    pytest.param("ground-team-manager", id="WSMG-CI-09"),
    pytest.param("finance", id="WSMG-CI-10"),
    pytest.param("Manager", id="WSMG-CI-11"),
    pytest.param("", id="WSMG-CI-12"),
])
def test_wsmg_ci_08_12__a_role_outside_the_invite_list_is_refused_and_nothing_is_written(db, t, w1, uo, role):
    """WSMG-CI-08 … WSMG-CI-12 — `owner`, `ground-team-manager`, `finance`, `Manager`, `""` are refused; nothing written.
    Rules: `create_invitation` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.ED, role=role, inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-13
def test_wsmg_ci_13__the_role_is_checked_before_the_workspace_is_looked_up(db, t, uo):
    """WSMG-CI-13 — the role is checked before the workspace is looked up.
    Rules: `create_invitation` R1, R5"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=MISSING, email=t.ED, role="finance", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-14
def test_wsmg_ci_14__an_active_member_s_email_is_refused_and_nothing_is_written(db, t, w1, uo, ua, mk_member):
    """WSMG-CI-14 — an active member's email is refused and nothing is written.
    Rules: `create_invitation` R3; Errors row 2; A3"""
    mk_member(ua)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-15
def test_wsmg_ci_15__an_account_with_no_row_in_the_workspace_may_be_invited(db, t, w1, uo):
    """WSMG-CI-15 — an account with no row in the workspace may be invited.
    Rules: `create_invitation` R3"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EA
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-16
def test_wsmg_ci_16__an_account_active_only_in_an_earlier_workspace_may_be_invited(db, t, w0, w1, uo, ua, mk_member):
    """WSMG-CI-16 — an account active only in an earlier workspace may be invited.
    Rules: `create_invitation` R3"""
    mk_member(ua, workspace_id=w0.id)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EA
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-17
def test_wsmg_ci_17__an_account_active_only_in_a_later_workspace_may_be_invited(db, t, w1, w2, uo, ua, mk_member):
    """WSMG-CI-17 — an account active only in a later workspace may be invited.
    Rules: `create_invitation` R3"""
    mk_member(ua, workspace_id=w2.id)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EA
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-18
def test_wsmg_ci_18__part_of_a_member_s_email_is_another_address(db, t, w1, uo, ua, mk_member):
    """WSMG-CI-18 — part of a member's email is another address.
    Rules: `create_invitation` R2, R3"""
    mk_member(ua)

    result = M.create_invitation(db, workspace_id=w1.id, email=f"nn.{t.TAG}@acme.com", role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == f"nn.{t.TAG}@acme.com"
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-19
def test_wsmg_ci_19__an_underscore_in_a_member_s_email_is_not_a_wildcard(db, t, w1, uo, mk_member):
    """WSMG-CI-19 — an underscore in a member's email is not a wildcard.
    Rules: `create_invitation` R2, R3"""
    p1 = make_profile(db, email=f"a_n.{t.TAG}@acme.com")
    mk_member(p1)

    result = M.create_invitation(db, workspace_id=w1.id, email=f"abn.{t.TAG}@acme.com", role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == f"abn.{t.TAG}@acme.com"
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-20
@BUG_1860
def test_wsmg_ci_20__a_member_s_email_in_other_capitals_is_recognised(db, t, w1, uo, ua, mk_member):
    """WSMG-CI-20 — a member's email in other capitals is recognised.
    Rules: `create_invitation` R2 [BUG-1860], R3"""
    mk_member(ua)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=f"ANN.{t.TAG.upper()}@ACME.COM", role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-21
@BUG_1860
def test_wsmg_ci_21__a_member_s_email_with_surrounding_spaces_is_recognised(db, t, w1, uo, ua, mk_member):
    """WSMG-CI-21 — a member's email with surrounding spaces is recognised.
    Rules: `create_invitation` R2 [BUG-1860], R3"""
    mk_member(ua)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=f"  {t.EA} ", role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-22
@BUG_1860
def test_wsmg_ci_22__an_account_stored_in_mixed_case_is_found_by_its_lower_case_email(db, t, w1, uo, mk_member):
    """WSMG-CI-22 — an account stored in mixed case is found by its lower-case email.
    Rules: `create_invitation` R2 [BUG-1860], R3"""
    p1 = make_profile(db, email=f"Zed.{t.TAG}@acme.com")
    mk_member(p1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=f"zed.{t.TAG}@acme.com", role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-23 … WSMG-CI-25: a row of any status but "inactive" is refused like an active one
@BUG_1983
@pytest.mark.parametrize("status", [
    pytest.param("suspended", id="WSMG-CI-23"),
    pytest.param("invited", id="WSMG-CI-24"),
    pytest.param("Inactive", id="WSMG-CI-25"),
])
def test_wsmg_ci_23_25__a_member_row_of_another_status_is_refused_like_an_active_one(
    db, t, w1, uo, ua, mk_member, status,
):
    """WSMG-CI-23 … WSMG-CI-25 — a member row with status `suspended`, `invited`, `Inactive` is refused like an active one.
    Rules: `create_invitation` R3a [BUG-1983]"""
    a = mk_member(ua, status=status)
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, a) == before_a


# [claude] WSMG-CI-26
def test_wsmg_ci_26__a_removed_inactive_member_may_be_invited_back(db, t, w1, uo, ua, mk_member):
    """WSMG-CI-26 — a removed (inactive) member may be invited back.
    Rules: `create_invitation` R3a"""
    a = mk_member(ua, status="inactive", left_at=T2)
    before_a = snap_before(db, a)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EA
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1
    # Then 4
    assert snap(db, a) == before_a


# [claude] WSMG-CI-27
@BUG_1873
def test_wsmg_ci_27__a_second_pending_invitation_to_the_same_email_is_refused(db, t, w1, uo, mk_invitation):
    """WSMG-CI-27 — a second pending invitation to the same email is refused.
    Rules: `create_invitation` R4 [BUG-1873]; Errors row 3; A3"""
    j = mk_invitation("J", t.ED)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "This email is already invited to this workspace"
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-28
@BUG_1873
def test_wsmg_ci_28__the_duplicate_check_ignores_capitals_in_the_new_email(db, t, w1, uo, mk_invitation):
    """WSMG-CI-28 — the duplicate check ignores capitals in the new email.
    Rules: `create_invitation` R4 [BUG-1873]"""
    mk_invitation("J", t.ED)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=f"DAN.{t.TAG.upper()}@ACME.COM", role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "This email is already invited to this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-29
@BUG_1873
def test_wsmg_ci_29__the_duplicate_check_trims_and_lower_cases_the_stored_email(db, t, w1, uo, mk_invitation):
    """WSMG-CI-29 — the duplicate check trims and lower-cases the stored email.
    Rules: `create_invitation` R4 [BUG-1873]"""
    mk_invitation("J", f" Dan.{t.TAG}@Acme.com ")
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "This email is already invited to this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-30
@BUG_1873
def test_wsmg_ci_30__a_pending_invitation_one_microsecond_from_expiry_still_blocks(db, t, w1, uo, mk_invitation):
    """WSMG-CI-30 — a pending invitation one microsecond from expiry still blocks.
    Rules: `create_invitation` R4 [BUG-1873]"""
    mk_invitation("J", t.ED, expires_at=NOW + US)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "This email is already invited to this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-31
def test_wsmg_ci_31__a_pending_invitation_expiring_exactly_now_does_not_block(db, t, w1, uo, mk_invitation):
    """WSMG-CI-31 — a pending invitation expiring exactly now does not block.
    Rules: `create_invitation` R4"""
    j = mk_invitation("J", t.ED, expires_at=NOW)
    before_j = snap_before(db, j)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1)) == 2
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-32
def test_wsmg_ci_32__an_accepted_invitation_to_the_same_email_does_not_block(db, t, w1, uo, mk_invitation):
    """WSMG-CI-32 — an accepted invitation to the same email does not block.
    Rules: `create_invitation` R4"""
    j = mk_invitation("J", t.ED, status="accepted")
    before_j = snap_before(db, j)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1)) == 2
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-33
def test_wsmg_ci_33__a_cancelled_invitation_to_the_same_email_does_not_block(db, t, w1, uo, mk_invitation):
    """WSMG-CI-33 — a cancelled invitation to the same email does not block.
    Rules: `create_invitation` R4"""
    j = mk_invitation("J", t.ED, status="cancelled")
    before_j = snap_before(db, j)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1)) == 2
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-34
def test_wsmg_ci_34__a_pending_invitation_in_an_earlier_workspace_does_not_block(db, t, w0, w1, uo, mk_invitation):
    """WSMG-CI-34 — a pending invitation to the same email in an earlier workspace does not block.
    Rules: `create_invitation` R4"""
    j = mk_invitation("J", t.ED, workspace_id=w0.id)
    before_j = snap_before(db, j)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-35
def test_wsmg_ci_35__a_pending_invitation_in_a_later_workspace_does_not_block(db, t, w1, w2, uo, mk_invitation):
    """WSMG-CI-35 — a pending invitation to the same email in a later workspace does not block.
    Rules: `create_invitation` R4"""
    j = mk_invitation("J", t.ED, workspace_id=w2.id)
    before_j = snap_before(db, j)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.ED
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-CI-36
def test_wsmg_ci_36__an_active_member_with_a_pending_invitation_gets_the_member_message(
    db, t, w1, uo, ua, mk_member, mk_invitation,
):
    """WSMG-CI-36 — an active member with a pending invitation gets the member message.
    Rules: `create_invitation` R3, R4"""
    mk_member(ua)
    mk_invitation("J", t.EA)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EA, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "User with this email is already a member of this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-37
@BUG_1873
def test_wsmg_ci_37__a_duplicate_invitation_on_a_full_workspace_gets_the_duplicate_message(
    db, t, w1, uo, set_limit, mk_invitation,
):
    """WSMG-CI-37 — a duplicate invitation on a full workspace gets the duplicate message, not the seat message.
    Rules: `create_invitation` R4 [BUG-1873], R7"""
    set_limit(2)
    mk_invitation("J", t.ED)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "This email is already invited to this workspace"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-38
def test_wsmg_ci_38__an_unknown_workspace_is_refused_and_nothing_is_written(db, t, uo):
    """WSMG-CI-38 — an unknown workspace is refused and nothing is written.
    Rules: `create_invitation` R5; Errors row 4; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=MISSING, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace not found"
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-39
def test_wsmg_ci_39__an_inactive_plan_s_limit_is_still_enforced(db, t, w1, uo, pl1, set_limit, mk_invitation):
    """WSMG-CI-39 — an inactive plan's limit is still enforced.
    Rules: `create_invitation` R6, R7"""
    set_limit(2)
    pl1.is_active = False
    db.flush()
    mk_invitation("J", t.ED)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-40
def test_wsmg_ci_40__at_the_limit_with_members_only_the_invitation_is_refused(db, t, w1, uo, ub, uc, set_limit, mk_member):
    """WSMG-CI-40 — at the limit with members only (3 active) the invitation is refused.
    Rules: `create_invitation` R7; Errors row 5; A3"""
    set_limit(3)
    mk_member(ub)
    mk_member(uc)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-41
def test_wsmg_ci_41__at_the_limit_with_members_and_a_pending_invitation_it_is_refused(
    db, t, w1, uo, ub, set_limit, mk_member, mk_invitation,
):
    """WSMG-CI-41 — at the limit with members and a pending invitation the invitation is refused.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_member(ub)
    mk_invitation("J", t.ED)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-42
def test_wsmg_ci_42__pending_invitations_alone_fill_the_seats_beside_the_owner(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-42 — pending invitations alone fill the seats beside the owner.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com")
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-43
def test_wsmg_ci_43__with_one_free_seat_the_invitation_is_created(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-43 — with one free seat the invitation is created.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-44
def test_wsmg_ci_44__above_the_limit_the_invitation_is_refused(db, t, w1, uo, ub, uc, set_limit, mk_member):
    """WSMG-CI-44 — above the limit (3 active on a limit of 2) the invitation is refused.
    Rules: `create_invitation` R7"""
    set_limit(2)
    mk_member(ub)
    mk_member(uc)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-45
def test_wsmg_ci_45__the_owner_alone_fills_a_limit_of_1(db, t, w1, uo, set_limit):
    """WSMG-CI-45 — the owner alone fills a limit of 1.
    Rules: `create_invitation` R7"""
    set_limit(1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-46
def test_wsmg_ci_46__a_pending_invitation_that_expired_exactly_now_frees_its_seat(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-46 — a pending invitation that expired exactly now frees its seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", expires_at=NOW)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 3


# [claude] WSMG-CI-47
def test_wsmg_ci_47__a_pending_invitation_one_microsecond_from_expiry_still_holds_its_seat(
    db, t, w1, uo, set_limit, mk_invitation,
):
    """WSMG-CI-47 — a pending invitation one microsecond from expiry still holds its seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", expires_at=NOW + US)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-48
def test_wsmg_ci_48__an_accepted_invitation_holds_no_seat(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-48 — an accepted invitation holds no seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", status="accepted")

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-49
def test_wsmg_ci_49__a_cancelled_invitation_holds_no_seat(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-49 — a cancelled invitation holds no seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", status="cancelled")

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-50
def test_wsmg_ci_50__a_suspended_member_holds_no_seat(db, t, w1, uo, ub, set_limit, mk_member, mk_invitation):
    """WSMG-CI-50 — a suspended member holds no seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_member(ub, status="suspended")
    mk_invitation("J", t.ED)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-51
def test_wsmg_ci_51__a_removed_inactive_member_holds_no_seat(db, t, w1, uo, ub, set_limit, mk_member, mk_invitation):
    """WSMG-CI-51 — a removed (inactive) member holds no seat.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_member(ub, status="inactive", left_at=T2)
    mk_invitation("J", t.ED)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-52
def test_wsmg_ci_52__members_and_invitations_of_an_earlier_workspace_hold_none_of_w1_s_seats(
    db, t, w0, w1, uo, ub, uc, set_limit, mk_member, mk_invitation,
):
    """WSMG-CI-52 — members and invitations of an earlier workspace hold none of W1's seats.
    Rules: `create_invitation` R7"""
    set_limit(2)
    mk_member(ub, workspace_id=w0.id)
    mk_member(uc, workspace_id=w0.id)
    mk_invitation("J", t.ED, workspace_id=w0.id)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", workspace_id=w0.id)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-53
def test_wsmg_ci_53__members_and_invitations_of_a_later_workspace_hold_none_of_w1_s_seats(
    db, t, w1, w2, uo, ub, uc, set_limit, mk_member, mk_invitation,
):
    """WSMG-CI-53 — members and invitations of a later workspace hold none of W1's seats.
    Rules: `create_invitation` R7"""
    set_limit(2)
    mk_member(ub, workspace_id=w2.id)
    mk_member(uc, workspace_id=w2.id)
    mk_invitation("J", t.ED, workspace_id=w2.id)
    mk_invitation("K", f"fay.{t.TAG}@acme.com", workspace_id=w2.id)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-54
def test_wsmg_ci_54__two_pending_invitations_to_one_email_hold_two_seats(db, t, w1, uo, set_limit, mk_invitation):
    """WSMG-CI-54 — two pending invitations to one email hold two seats.
    Rules: `create_invitation` R7"""
    set_limit(3)
    mk_invitation("J", t.ED)
    mk_invitation("K", t.ED)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."
    # Then 3
    assert written(db) == before


# [claude] WSMG-CI-55
@BUG_1871
def test_wsmg_ci_55__a_limit_of_minus_1_means_no_limit(db, t, w1, uo, ub, set_limit, mk_member, mk_invitation):
    """WSMG-CI-55 — a limit of -1 means no limit.
    Rules: `create_invitation` R8 [BUG-1871]"""
    set_limit(-1)
    mk_member(ub)
    mk_invitation("J", t.ED)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 2


# [claude] WSMG-CI-56
@BUG_1871
def test_wsmg_ci_56__a_limit_of_minus_5_means_no_limit(db, t, w1, uo, set_limit):
    """WSMG-CI-56 — a limit of -5 means no limit.
    Rules: `create_invitation` R8 [BUG-1871]"""
    set_limit(-5)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.email == t.EE
    assert row.status == "pending"
    # Then 3
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-CI-57
def test_wsmg_ci_57__one_invitation_sent_audit_row_carries_the_email_as_given(db, t, w1, uo):
    """WSMG-CI-57 — one invitation_sent audit row carries the email as given.
    Rules: `create_invitation` R13; A1"""
    result = M.create_invitation(db, workspace_id=w1.id, email=f"Dan.{t.TAG}@Acme.COM", role="viewer", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].user_id == uo.id
    assert rows[0].action == "invitation_sent"
    assert rows[0].metadata_json == {"email": f"Dan.{t.TAG}@Acme.COM", "role": "viewer"}
    # Then 4
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None


# [claude] WSMG-CI-58
def test_wsmg_ci_58__with_no_inviter_the_invitation_and_the_audit_row_carry_no_actor(db, t, w1):
    """WSMG-CI-58 — with no inviter the invitation and the audit row carry no actor.
    Rules: `create_invitation` R10, R13"""
    result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.invited_by_user_id is None
    # Then 3
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id is None
    assert rows[0].action == "invitation_sent"


# [claude] WSMG-CI-59
def test_wsmg_ci_59__create_invitation_flushes_and_never_commits(db, t, w1, uo):
    """WSMG-CI-59 — create_invitation flushes and never commits.
    Rules: `create_invitation` Returns; Side effects"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.create_invitation(db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(invitations(db, w1)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert len(invitations(db, w1)) == 0


# [claude] WSMG-CI-60
@BUG_1404
def test_wsmg_ci_60__the_audit_row_carries_the_request_s_ip_address_and_user_agent(db, t, w1, uo):
    """WSMG-CI-60 — the audit row carries the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `create_invitation` R13"""
    result = M.create_invitation(
        db, workspace_id=w1.id, email=t.ED, role="member", inviter_id=uo.id,
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# --------------------------------------------------------------------------- #
# WorkspaceManager.validate_invitation_for_user
# --------------------------------------------------------------------------- #

# [claude] WSMG-VI-01
def test_wsmg_vi_01__a_pending_unexpired_invitation_for_this_email_is_returned_unchanged(db, t, mk_invitation):
    """WSMG-VI-01 — a pending, unexpired invitation for this email is returned unchanged.
    Rules: `validate_invitation_for_user` R1–R6, Returns"""
    i = mk_invitation("I", t.EA)
    before_i = snap_before(db, i)
    before = written(db)

    result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == i.id
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-VI-02
def test_wsmg_vi_02__validation_writes_nothing_and_leaves_the_caller_s_pending_row_alone(db, t, w1, mk_invitation):
    """WSMG-VI-02 — validation writes nothing and leaves the caller's pending row alone.
    Rules: `validate_invitation_for_user` R6; Side effects"""
    i = mk_invitation("I", t.EA)
    p = Department(workspace_id=w1.id, name="Spare")
    db.add(p)

    result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)

    # Then 1
    assert result.id == i.id
    # Then 2
    assert len(db.new) == 1
    # Then 3
    assert p in db.new
    # Then 4
    assert not db.dirty
    # Then 5
    assert not db.deleted


# [claude] WSMG-VI-03
def test_wsmg_vi_03__an_unknown_token_is_refused(db, t, mk_invitation):
    """WSMG-VI-03 — an unknown token is refused.
    Rules: `validate_invitation_for_user` R1; Errors row 1"""
    i = mk_invitation("I", t.EA)
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-X-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invalid invitation token"
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-04
def test_wsmg_vi_04__the_token_in_capitals_is_unknown(db, t, mk_invitation):
    """WSMG-VI-04 — the token in capitals is unknown.
    Rules: `validate_invitation_for_user` R1"""
    mk_invitation("I", t.EA)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}".upper(), user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invalid invitation token"


# [claude] WSMG-VI-05
def test_wsmg_vi_05__the_token_with_a_leading_space_is_unknown(db, t, mk_invitation):
    """WSMG-VI-05 — the token with a leading space is unknown.
    Rules: `validate_invitation_for_user` R1"""
    mk_invitation("I", t.EA)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=" " + f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invalid invitation token"


# [claude] WSMG-VI-06
def test_wsmg_vi_06__an_invitation_of_another_workspace_is_found_by_its_token_alone(db, t, w2, mk_invitation):
    """WSMG-VI-06 — an invitation of another workspace is found by its token alone.
    Rules: `validate_invitation_for_user` R1, R6"""
    i = mk_invitation("I", t.EA, workspace_id=w2.id)

    result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == i.id
    # Then 3
    assert result.workspace_id == w2.id


# [claude] WSMG-VI-07
def test_wsmg_vi_07__an_invitation_that_expired_a_microsecond_ago_is_refused(db, t, mk_invitation):
    """WSMG-VI-07 — an invitation that expired a microsecond ago is refused.
    Rules: `validate_invitation_for_user` R2; Errors row 2"""
    i = mk_invitation("I", t.EA, expires_at=NOW - US)
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has expired. Please request a new invitation."
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-08
@BUG_1987
def test_wsmg_vi_08__an_invitation_expiring_exactly_now_is_expired(db, t, mk_invitation):
    """WSMG-VI-08 — an invitation expiring exactly now is expired.
    Rules: `validate_invitation_for_user` R2 [BUG-1987]"""
    mk_invitation("I", t.EA, expires_at=NOW)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has expired. Please request a new invitation."


# [claude] WSMG-VI-09
def test_wsmg_vi_09__an_invitation_expiring_a_microsecond_from_now_passes(db, t, mk_invitation):
    """WSMG-VI-09 — an invitation expiring a microsecond from now passes.
    Rules: `validate_invitation_for_user` R2"""
    i = mk_invitation("I", t.EA, expires_at=NOW + US)

    result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == i.id


# [claude] WSMG-VI-10
def test_wsmg_vi_10__an_accepted_invitation_that_has_also_expired_gets_the_expiry_message(db, t, mk_invitation):
    """WSMG-VI-10 — an accepted invitation that has also expired gets the expiry message.
    Rules: `validate_invitation_for_user` R3"""
    mk_invitation("I", t.EA, status="accepted", expires_at=NOW - DAY)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has expired. Please request a new invitation."


# [claude] WSMG-VI-11
def test_wsmg_vi_11__a_cancelled_invitation_that_has_also_expired_gets_the_expiry_message(db, t, mk_invitation):
    """WSMG-VI-11 — a cancelled invitation that has also expired gets the expiry message.
    Rules: `validate_invitation_for_user` R3"""
    mk_invitation("I", t.EA, status="cancelled", expires_at=NOW - DAY)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has expired. Please request a new invitation."


# [claude] WSMG-VI-12
def test_wsmg_vi_12__an_unexpired_accepted_invitation_is_refused_with_its_status(db, t, mk_invitation):
    """WSMG-VI-12 — an unexpired invitation with status "accepted" is refused with its status.
    Rules: `validate_invitation_for_user` R4; Errors row 3"""
    i = mk_invitation("I", t.EA, status="accepted")
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has already been accepted"
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-13
def test_wsmg_vi_13__an_unexpired_cancelled_invitation_is_refused_with_its_status(db, t, mk_invitation):
    """WSMG-VI-13 — an unexpired invitation with status "cancelled" is refused with its status.
    Rules: `validate_invitation_for_user` R4; Errors row 3"""
    i = mk_invitation("I", t.EA, status="cancelled")
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has already been cancelled"
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-14
def test_wsmg_vi_14__an_unexpired_expired_status_invitation_is_refused_with_its_status(db, t, mk_invitation):
    """WSMG-VI-14 — an unexpired invitation with status "expired" is refused with its status.
    Rules: `validate_invitation_for_user` R4; Errors row 3"""
    i = mk_invitation("I", t.EA, status="expired")
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has already been expired"
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-15
def test_wsmg_vi_15__an_unexpired_pending_in_capitals_invitation_is_refused_with_its_status(db, t, mk_invitation):
    """WSMG-VI-15 — an unexpired invitation with status "Pending" is refused with its status.
    Rules: `validate_invitation_for_user` R4; Errors row 3"""
    i = mk_invitation("I", t.EA, status="Pending")
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)
    # Then 2
    assert str(exc.value) == "Invitation has already been Pending"
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-16
def test_wsmg_vi_16__another_person_s_email_is_refused_naming_both_emails(db, t, mk_invitation):
    """WSMG-VI-16 — another person's email is refused, naming both emails.
    Rules: `validate_invitation_for_user` R5; Errors row 4"""
    i = mk_invitation("I", t.EA)
    before_i = snap_before(db, i)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EB)
    # Then 2
    assert str(exc.value) == f"This invitation was sent to {t.EA}. You cannot accept it with {t.EB}."
    # Then 3
    assert snap(db, i) == before_i


# [claude] WSMG-VI-17
def test_wsmg_vi_17__the_same_email_in_other_capitals_passes(db, t, mk_invitation):
    """WSMG-VI-17 — the same email in other capitals passes.
    Rules: `validate_invitation_for_user` R5"""
    i = mk_invitation("I", t.EA)

    result = M.validate_invitation_for_user(
        db, invitation_token=f"tok-I-{t.TAG}", user_email=f"ANN.{t.TAG.upper()}@ACME.COM",
    )

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == i.id


# [claude] WSMG-VI-18
def test_wsmg_vi_18__a_stored_email_in_mixed_capitals_matches_the_lower_case_email(db, t, mk_invitation):
    """WSMG-VI-18 — a stored email in mixed capitals matches the lower-case email.
    Rules: `validate_invitation_for_user` R5"""
    i = mk_invitation("I", f"Ann.{t.TAG}@Acme.com")

    result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EA)

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == i.id


# [claude] WSMG-VI-19
def test_wsmg_vi_19__surrounding_spaces_are_not_removed_from_the_user_s_email(db, t, mk_invitation):
    """WSMG-VI-19 — surrounding spaces are not removed from the user's email.
    Rules: `validate_invitation_for_user` R5"""
    mk_invitation("I", t.EA)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=" " + t.EA)
    # Then 2
    assert str(exc.value) == f"This invitation was sent to {t.EA}. You cannot accept it with  {t.EA}."


# [claude] WSMG-VI-20
def test_wsmg_vi_20__part_of_the_invited_email_does_not_match(db, t, mk_invitation):
    """WSMG-VI-20 — part of the invited email does not match.
    Rules: `validate_invitation_for_user` R5"""
    mk_invitation("I", t.EA)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=f"nn.{t.TAG}@acme.com")
    # Then 2
    assert str(exc.value) == f"This invitation was sent to {t.EA}. You cannot accept it with nn.{t.TAG}@acme.com."


# [claude] WSMG-VI-21
def test_wsmg_vi_21__the_status_is_checked_before_the_email(db, t, mk_invitation):
    """WSMG-VI-21 — the status is checked before the email.
    Rules: `validate_invitation_for_user` R6"""
    mk_invitation("I", t.EA, status="accepted")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EB)
    # Then 2
    assert str(exc.value) == "Invitation has already been accepted"


# [claude] WSMG-VI-22
def test_wsmg_vi_22__expiry_is_checked_before_the_email(db, t, mk_invitation):
    """WSMG-VI-22 — expiry is checked before the email.
    Rules: `validate_invitation_for_user` R6"""
    mk_invitation("I", t.EA, expires_at=NOW - DAY)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.validate_invitation_for_user(db, invitation_token=f"tok-I-{t.TAG}", user_email=t.EB)
    # Then 2
    assert str(exc.value) == "Invitation has expired. Please request a new invitation."


# --------------------------------------------------------------------------- #
# WorkspaceManager.accept_invitation
# --------------------------------------------------------------------------- #

# [claude] WSMG-AI-01
def test_wsmg_ai_01__accepting_makes_the_user_a_member_with_the_invitation_s_role_and_position(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-01 — accepting makes the user a member with the invitation's role and position.
    Rules: `accept_invitation` R3, Returns"""
    i = mk_invitation("I", t.EA, role="manager", position="Lead")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    row = reread(db, result)
    assert row.role == "manager"
    assert row.position == "Lead"
    assert row.joined_at == NOW
    assert row.left_at is None
    # Then 4
    assert len(members(db, w1, ua)) == 1


# [claude] WSMG-AI-02
def test_wsmg_ai_02__the_invitation_is_marked_accepted_by_the_user_nothing_else_changes_on_it(
    db, t, ua, mk_invitation,
):
    """WSMG-AI-02 — the invitation is marked accepted by the user, nothing else changes on it.
    Rules: `accept_invitation` R4"""
    i = mk_invitation("I", t.EA, role="manager", position="Lead")
    before_i = snap_before(db, i)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, i)
    assert row.status == "accepted"
    assert row.accepted_at == NOW
    assert row.accepted_by_user_id == ua.id
    # Then 3
    changed = ("status", "accepted_at", "accepted_by_user_id")
    assert without(snap(db, i), *changed) == without(before_i, *changed)


# [claude] WSMG-AI-03
def test_wsmg_ai_03__a_successful_accept_writes_member_added_and_invitation_accepted(
    db, t, w1, uo, ua, mk_invitation,
):
    """WSMG-AI-03 — a successful accept writes member_added and invitation_accepted.
    Rules: `accept_invitation` R3, R6; A1"""
    i = mk_invitation("I", t.EA, role="manager", position="Lead")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(audit(db, w1)) == 2
    # Then 3
    rows = audit(db, w1, "member_added")
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == uo.id
    assert rows[0].metadata_json == {"new_member_id": ua.id, "role": "manager"}
    # Then 5
    rows = audit(db, w1, "invitation_accepted")
    assert len(rows) == 1
    # Then 6
    assert rows[0].user_id == ua.id
    assert rows[0].metadata_json == {"invitation_id": i.id}
    # Then 7
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None


# [claude] WSMG-AI-04
def test_wsmg_ai_04__an_unknown_invitation_id_is_refused_and_nothing_is_written(db, ua):
    """WSMG-AI-04 — an unknown invitation id is refused and nothing is written.
    Rules: `accept_invitation` R1; Errors row 1; A3"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.accept_invitation(db, invitation_id=MISSING, user_id=ua.id)
    # Then 2
    assert str(exc.value) == "Invitation not found"
    # Then 3
    assert written(db) == before


# [claude] WSMG-AI-05
def test_wsmg_ai_05__an_already_accepted_invitation_is_not_checked_here_and_still_adds_the_user(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-05 — an already accepted invitation is not checked here and still adds the user.
    Rules: `accept_invitation` R2"""
    i = mk_invitation("I", t.EA, status="accepted")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    inv = reread(db, i)
    assert inv.status == "accepted"
    assert inv.accepted_by_user_id == ua.id


# [claude] WSMG-AI-06
def test_wsmg_ai_06__a_cancelled_invitation_is_not_checked_here_and_still_adds_the_user(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-06 — a cancelled invitation is not checked here and still adds the user.
    Rules: `accept_invitation` R2"""
    i = mk_invitation("I", t.EA, status="cancelled")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    inv = reread(db, i)
    assert inv.status == "accepted"
    assert inv.accepted_by_user_id == ua.id


# [claude] WSMG-AI-07
def test_wsmg_ai_07__an_expired_invitation_is_not_checked_here_and_still_adds_the_user(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-07 — an expired invitation is not checked here and still adds the user.
    Rules: `accept_invitation` R2"""
    i = mk_invitation("I", t.EA, expires_at=NOW - DAY)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    inv = reread(db, i)
    assert inv.status == "accepted"
    assert inv.accepted_by_user_id == ua.id


# [claude] WSMG-AI-08
def test_wsmg_ai_08__the_member_is_added_to_the_invitation_s_own_workspace(db, t, w1, w2, ua, mk_invitation):
    """WSMG-AI-08 — the member is added to the invitation's own workspace.
    Rules: `accept_invitation` R3"""
    i = mk_invitation("I", t.EA, workspace_id=w2.id)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.workspace_id == w2.id
    # Then 2
    assert len(members(db, w2, ua)) == 1
    # Then 3
    assert len(members(db, w1, ua)) == 0
    # Then 4
    assert len(audit(db, w2)) == 2
    # Then 5
    assert len(audit(db, w1)) == 0


# [claude] WSMG-AI-09
def test_wsmg_ai_09__an_invitation_with_no_inviter_adds_a_member_with_no_actor(db, t, w1, ua, mk_invitation):
    """WSMG-AI-09 — an invitation with no inviter adds a member with no actor.
    Rules: `accept_invitation` R3"""
    i = mk_invitation("I", t.EA, invited_by_user_id=None)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    row = reread(db, result)
    assert row.invited_by_user_id is None
    # Then 4
    rows = audit(db, w1, "member_added")
    assert len(rows) == 1
    # Then 5
    assert rows[0].user_id is None


# [claude] WSMG-AI-10
@BUG_1985
def test_wsmg_ai_10__the_new_member_row_records_the_invitation_s_inviter(db, t, uo, ua, mk_invitation):
    """WSMG-AI-10 — the new member row records the invitation's inviter.
    Rules: `accept_invitation` R3 [BUG-1985]"""
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.invited_by_user_id == uo.id


# [claude] WSMG-AI-11
def test_wsmg_ai_11__an_active_member_cannot_accept_the_invitation_is_left_unchanged(
    db, t, ua, mk_member, mk_invitation,
):
    """WSMG-AI-11 — an active member cannot accept; the invitation is left unchanged.
    Rules: `accept_invitation` R3; Errors row 2; A3"""
    a = mk_member(ua)
    i = mk_invitation("I", t.EA)
    before_i = snap_before(db, i)
    before_a = snap_before(db, a)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)
    # Then 2
    assert str(exc.value) == "User is already a member of this workspace"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] WSMG-AI-12
def test_wsmg_ai_12__a_full_workspace_refuses_the_accept_the_invitation_is_left_unchanged(
    db, t, ua, ub, set_limit, mk_member, mk_invitation,
):
    """WSMG-AI-12 — a full workspace refuses the accept; the invitation is left unchanged.
    Rules: `accept_invitation` R3; Errors row 2"""
    set_limit(2)
    mk_member(ub)
    i = mk_invitation("I", t.EA)
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)
    # Then 2
    assert str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-AI-13
def test_wsmg_ai_13__pending_invitations_do_not_take_a_seat_at_accept(
    db, t, w1, ua, ub, set_limit, mk_member, mk_invitation,
):
    """WSMG-AI-13 — pending invitations do not take a seat at accept.
    Rules: `accept_invitation` R3"""
    set_limit(3)
    mk_member(ub)
    i = mk_invitation("I", t.EA)
    j = mk_invitation("J", t.ED)
    before_j = snap_before(db, j)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"
    # Then 3
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 3
    # Then 4
    assert snap(db, j) == before_j


# [claude] WSMG-AI-14
@BUG_1872
def test_wsmg_ai_14__a_limit_of_minus_1_does_not_refuse_the_accept(
    db, t, w1, ua, ub, uc, set_limit, mk_member, mk_invitation,
):
    """WSMG-AI-14 — a limit of -1 does not refuse the accept.
    Rules: `accept_invitation` R3 [BUG-1872]"""
    set_limit(-1)
    mk_member(ub)
    mk_member(uc)
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert isinstance(result, WorkspaceMember)
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.user_id == ua.id
    assert row.status == "active"


# [claude] WSMG-AI-15
@BUG_1982
def test_wsmg_ai_15__a_removed_member_who_accepts_gets_their_old_row_back(db, t, w1, ua, mk_member, mk_invitation):
    """WSMG-AI-15 — a removed member who accepts gets their old row back.
    Rules: `accept_invitation` R3 [BUG-1982]"""
    a = mk_member(ua, role="viewer", status="inactive", joined_at=T1, left_at=T2)
    i = mk_invitation("I", t.EA, role="manager", position="Lead")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.status == "active"
    assert row.role == "manager"
    assert row.position == "Lead"
    assert row.left_at is None
    # Then 3
    assert len(members(db, w1, ua)) == 1
    # Then 4
    assert reread(db, i).status == "accepted"


# [claude] WSMG-AI-16
@BUG_1874
def test_wsmg_ai_16__another_pending_invitation_to_the_same_email_is_cancelled_as_superseded(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-16 — another pending invitation to the same email is cancelled as superseded.
    Rules: `accept_invitation` R5 [BUG-1874]"""
    j = mk_invitation("J", t.EA)
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, j).status == "cancelled"
    # Then 3
    rows = audit(db, w1, "invitation_cancelled")
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == ua.id
    assert rows[0].metadata_json == {"invitation_id": j.id, "email": t.EA, "reason": "superseded"}
    # Then 5
    assert len(audit(db, w1)) == 3


# [claude] WSMG-AI-17
@BUG_1874
def test_wsmg_ai_17__an_expired_pending_invitation_to_the_same_email_is_cancelled_too(db, t, ua, mk_invitation):
    """WSMG-AI-17 — an expired pending invitation to the same email is cancelled too.
    Rules: `accept_invitation` R5 [BUG-1874]"""
    i = mk_invitation("I", t.EA)
    k = mk_invitation("K", t.EA, expires_at=NOW - DAY)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, k).status == "cancelled"


# [claude] WSMG-AI-18
@BUG_1874
def test_wsmg_ai_18__a_pending_invitation_to_the_same_email_in_other_capitals_is_cancelled(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-18 — a pending invitation to the same email in other capitals is cancelled.
    Rules: `accept_invitation` R5 [BUG-1874]"""
    i = mk_invitation("I", t.EA)
    k = mk_invitation("K", f"Ann.{t.TAG}@Acme.com")

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, k).status == "cancelled"
    # Then 3
    rows = audit(db, w1, "invitation_cancelled")
    assert len(rows) == 1
    # Then 4
    assert rows[0].user_id == ua.id
    assert rows[0].metadata_json == {"invitation_id": k.id, "email": f"Ann.{t.TAG}@Acme.com", "reason": "superseded"}


# [claude] WSMG-AI-19
def test_wsmg_ai_19__a_pending_invitation_to_the_same_email_in_an_earlier_workspace_is_not_touched(
    db, t, w0, ua, mk_invitation,
):
    """WSMG-AI-19 — a pending invitation to the same email in an earlier workspace is not touched.
    Rules: `accept_invitation` R5"""
    j = mk_invitation("J", t.EA, workspace_id=w0.id)
    i = mk_invitation("I", t.EA)
    before_j = snap_before(db, j)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert len(audit(db, w0)) == 0


# [claude] WSMG-AI-20
def test_wsmg_ai_20__a_pending_invitation_to_the_same_email_in_a_later_workspace_is_not_touched(
    db, t, w2, ua, mk_invitation,
):
    """WSMG-AI-20 — a pending invitation to the same email in a later workspace is not touched.
    Rules: `accept_invitation` R5"""
    j = mk_invitation("J", t.EA, workspace_id=w2.id)
    i = mk_invitation("I", t.EA)
    before_j = snap_before(db, j)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert len(audit(db, w2)) == 0


# [claude] WSMG-AI-21
def test_wsmg_ai_21__a_pending_invitation_to_another_email_is_not_touched(db, t, w1, ua, mk_invitation):
    """WSMG-AI-21 — a pending invitation to another email is not touched.
    Rules: `accept_invitation` R5"""
    j = mk_invitation("J", t.EB)
    i = mk_invitation("I", t.EA)
    before_j = snap_before(db, j)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert len(audit(db, w1, "invitation_cancelled")) == 0


# [claude] WSMG-AI-22
def test_wsmg_ai_22__accepted_and_cancelled_invitations_to_the_same_email_are_not_touched(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-22 — accepted and cancelled invitations to the same email are not touched.
    Rules: `accept_invitation` R5"""
    j = mk_invitation("J", t.EA, status="accepted")
    k = mk_invitation("K", t.EA, status="cancelled")
    i = mk_invitation("I", t.EA)
    before_j = snap_before(db, j)
    before_k = snap_before(db, k)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert snap(db, k) == before_k
    # Then 4
    assert len(audit(db, w1, "invitation_cancelled")) == 0


# [claude] WSMG-AI-23
def test_wsmg_ai_23__an_unknown_user_fails_at_the_member_insert_the_invitation_stays_pending(
    db, t, mk_invitation,
):
    """WSMG-AI-23 — an unknown user fails at the member insert; the invitation stays pending.
    Rules: `accept_invitation` R3 (add R10)"""
    i = mk_invitation("I", t.EA)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.accept_invitation(db, invitation_id=i.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    row = reread(db, i)
    assert row.status == "pending"
    assert row.accepted_at is None
    assert row.accepted_by_user_id is None


# [claude] WSMG-AI-24
def test_wsmg_ai_24__accept_flushes_and_never_commits(db, t, w1, ua, mk_invitation):
    """WSMG-AI-24 — accept flushes and never commits.
    Rules: `accept_invitation` Returns; Side effects"""
    i = mk_invitation("I", t.EA)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(members(db, w1, ua)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert len(members(db, w1, ua)) == 0
    # Then 5
    assert reread(db, i).status == "pending"


# [claude] WSMG-AI-25
@BUG_1404
def test_wsmg_ai_25__both_audit_rows_carry_the_request_s_ip_address_and_user_agent(db, t, w1, ua, mk_invitation):
    """WSMG-AI-25 — both audit rows carry the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `accept_invitation` R6"""
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(
        db, invitation_id=i.id, user_id=ua.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 2
    # Then 3
    for row in rows:
        assert row.ip_address == "203.0.113.7"
        assert row.user_agent == "Mozilla/5.0 Test"


# [claude] WSMG-AI-26
def test_wsmg_ai_26__the_accept_writes_member_added_before_invitation_accepted(db, t, w1, ua, mk_invitation):
    """WSMG-AI-26 — the accept writes member_added before invitation_accepted.
    Rules: `accept_invitation` R6a"""
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert [r.action for r in audit(db, w1)] == ["member_added", "invitation_accepted"]


# [claude] WSMG-AI-27
@BUG_1874
def test_wsmg_ai_27__superseded_invitations_are_logged_after_the_acceptance_by_ascending_id(
    db, t, w1, ua, mk_invitation,
):
    """WSMG-AI-27 — superseded invitations are logged after the acceptance, by ascending invitation id.
    Rules: `accept_invitation` R6a, R5 [BUG-1874]"""
    j = mk_invitation("J", t.EA)
    i = mk_invitation("I", t.EA)
    k = mk_invitation("K", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert [r.action for r in audit(db, w1)] == [
        "member_added", "invitation_accepted", "invitation_cancelled", "invitation_cancelled",
    ]
    # Then 3
    assert [r.metadata_json["invitation_id"] for r in audit(db, w1, "invitation_cancelled")] == [j.id, k.id]


# [claude] WSMG-AI-28
@BUG_1404_AND_1874
def test_wsmg_ai_28__every_audit_row_of_an_accept_carries_ip_address_and_user_agent(db, t, w1, ua, mk_invitation):
    """WSMG-AI-28 — every audit row of an accept, the superseded ones included, carries IP address and user agent.
    Rules: `accept_invitation` R6a; A2 [BUG-1404]; R5 [BUG-1874]"""
    i = mk_invitation("I", t.EA)
    mk_invitation("J", t.EA)

    result = M.accept_invitation(
        db, invitation_id=i.id, user_id=ua.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    rows = audit(db, w1)
    assert len(rows) == 3
    # Then 3
    for row in rows:
        assert row.ip_address == "203.0.113.7"
        assert row.user_agent == "Mozilla/5.0 Test"


# --------------------------------------------------------------------------- #
# WorkspaceManager.cancel_invitation
# (owner only; another workspace's invitation and an unknown id answer alike, BUG-1981;
# a non-owner hears the owner message first, BUG-1986)
# --------------------------------------------------------------------------- #


# [claude] WSMG-XI-01
def test_wsmg_xi_01__the_owner_cancels_a_pending_invitation_only_its_status_changes(db, t, w1, uo, mk_invitation):
    """WSMG-XI-01 — the owner cancels a pending invitation; only its status changes.
    Rules: `cancel_invitation` R5"""
    i = mk_invitation("I", t.ED)
    before_i = snap_before(db, i)

    result = M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)

    # Then 1
    row = reread(db, i)
    assert row.status == "cancelled"
    # Then 2
    assert without(snap(db, i), "status") == without(before_i, "status")
    # Then 3
    assert result is None


# [claude] WSMG-XI-02
def test_wsmg_xi_02__one_invitation_cancelled_audit_row_names_the_invitation_and_its_email(
    db, t, w1, uo, mk_invitation,
):
    """WSMG-XI-02 — one invitation_cancelled audit row names the invitation and its email.
    Rules: `cancel_invitation` R6; A1"""
    i = mk_invitation("I", t.ED)

    result = M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)

    # Then 1
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 2
    assert rows[0].user_id == uo.id
    assert rows[0].action == "invitation_cancelled"
    assert rows[0].metadata_json == {"invitation_id": i.id, "email": t.ED}
    # Then 3
    assert rows[0].resource_type is None
    assert rows[0].resource_id is None
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None
    # Then 4
    assert result is None


# [claude] WSMG-XI-03
def test_wsmg_xi_03__an_expired_pending_invitation_can_still_be_cancelled(db, t, w1, uo, mk_invitation):
    """WSMG-XI-03 — an expired pending invitation can still be cancelled.
    Rules: `cancel_invitation` R4"""
    i = mk_invitation("I", t.ED, expires_at=NOW - DAY)

    result = M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)

    # Then 1
    row = reread(db, i)
    assert row.status == "cancelled"
    # Then 2
    assert len(audit(db, w1)) == 1
    # Then 3
    assert result is None


# [claude] WSMG-XI-04
def test_wsmg_xi_04__an_invitation_with_status_accepted_cannot_be_cancelled(db, t, w1, uo, mk_invitation):
    """WSMG-XI-04 — an invitation with status "accepted" cannot be cancelled.
    Rules: `cancel_invitation` R3; Errors row 3; A3"""
    i = mk_invitation("I", t.ED, status="accepted")
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Cannot cancel invitation that is accepted"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-05
def test_wsmg_xi_05__an_invitation_with_status_cancelled_cannot_be_cancelled(db, t, w1, uo, mk_invitation):
    """WSMG-XI-05 — an invitation with status "cancelled" cannot be cancelled.
    Rules: `cancel_invitation` R3; Errors row 3; A3"""
    i = mk_invitation("I", t.ED, status="cancelled")
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Cannot cancel invitation that is cancelled"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-06
def test_wsmg_xi_06__an_invitation_with_status_pending_in_capitals_cannot_be_cancelled(db, t, w1, uo, mk_invitation):
    """WSMG-XI-06 — an invitation with status "Pending" cannot be cancelled.
    Rules: `cancel_invitation` R3; Errors row 3; A3"""
    i = mk_invitation("I", t.ED, status="Pending")
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Cannot cancel invitation that is Pending"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-07
def test_wsmg_xi_07__an_unknown_invitation_id_is_refused(db, t, w1, uo, mk_invitation):
    """WSMG-XI-07 — an unknown invitation id is refused.
    Rules: `cancel_invitation` R2; Errors row 2; A3"""
    i = mk_invitation("I", t.ED)
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=MISSING, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Invitation not found"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-08
@BUG_1981
def test_wsmg_xi_08__an_invitation_of_a_later_workspace_answers_as_not_found(db, t, w1, w2, uo, mk_invitation):
    """WSMG-XI-08 — an invitation of a later workspace answers as not found.
    Rules: `cancel_invitation` R2 [BUG-1981] (HR-16)"""
    j = mk_invitation("J", t.ED, workspace_id=w2.id)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=j.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Invitation not found"
    # Then 3
    assert snap(db, j) == before_j
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-09
def test_wsmg_xi_09__an_invitation_of_a_later_workspace_is_refused_and_left_unchanged(
    db, t, w1, w2, uo, mk_invitation,
):
    """WSMG-XI-09 — an invitation of a later workspace is refused and left unchanged.
    Rules: `cancel_invitation` R2 (HR-16)"""
    j = mk_invitation("J", t.ED, workspace_id=w2.id)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1 (the message is checked in the BUG-1981 card)
    with pytest.raises(ValueError):
        M.cancel_invitation(db, invitation_id=j.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert written(db) == before


# [claude] WSMG-XI-10
@BUG_1981
def test_wsmg_xi_10__an_invitation_of_an_earlier_workspace_answers_as_not_found(db, t, w0, w1, uo, mk_invitation):
    """WSMG-XI-10 — an invitation of an earlier workspace answers as not found.
    Rules: `cancel_invitation` R2 [BUG-1981] (HR-16)"""
    j = mk_invitation("J", t.ED, workspace_id=w0.id)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=j.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Invitation not found"
    # Then 3
    assert snap(db, j) == before_j
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-11
def test_wsmg_xi_11__an_invitation_of_an_earlier_workspace_is_refused_and_left_unchanged(
    db, t, w0, w1, uo, mk_invitation,
):
    """WSMG-XI-11 — an invitation of an earlier workspace is refused and left unchanged.
    Rules: `cancel_invitation` R2 (HR-16)"""
    j = mk_invitation("J", t.ED, workspace_id=w0.id)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1 (the message is checked in the BUG-1981 card)
    with pytest.raises(ValueError):
        M.cancel_invitation(db, invitation_id=j.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)
    # Then 2
    assert snap(db, j) == before_j
    # Then 3
    assert written(db) == before


# [claude] WSMG-XI-12 … WSMG-XI-19 (same setup and checks; only the caller's role differs)
@pytest.mark.parametrize("role", [
    pytest.param("manager", id="WSMG-XI-12"),
    pytest.param("member", id="WSMG-XI-13"),
    pytest.param("viewer", id="WSMG-XI-14"),
    pytest.param("ground-team", id="WSMG-XI-15"),
    pytest.param("ground-team-manager", id="WSMG-XI-16"),
    pytest.param("finance", id="WSMG-XI-17"),
    pytest.param("Owner", id="WSMG-XI-18"),
    pytest.param("", id="WSMG-XI-19"),
])
def test_wsmg_xi_12_to_19__a_role_other_than_exactly_owner_may_not_cancel(
    db, t, w1, ub, mk_member, mk_invitation, role,
):
    """WSMG-XI-12 … WSMG-XI-19 — the roles "manager", "member", "viewer", "ground-team",
    "ground-team-manager", "finance", "Owner" and "" may not cancel.
    Rules: `cancel_invitation` R1; Errors row 1; A3"""
    i = mk_invitation("I", t.ED)
    mk_member(ub, role=role)
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=ub.id, canceller_role=role, workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-20
@BUG_1986
def test_wsmg_xi_20__a_non_owner_asking_about_an_unknown_id_gets_the_owner_message(db, w1, ub, mk_member):
    """WSMG-XI-20 — a non-owner asking about an unknown id gets the owner message.
    Rules: `cancel_invitation` R1 [BUG-1986]"""
    mk_member(ub)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=MISSING, canceller_id=ub.id, canceller_role="member", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert written(db) == before


# [claude] WSMG-XI-21
@BUG_1986
def test_wsmg_xi_21__a_non_owner_asking_about_another_workspace_s_invitation_gets_the_owner_message(
    db, t, w1, w2, ub, mk_member, mk_invitation,
):
    """WSMG-XI-21 — a non-owner asking about another workspace's invitation gets the owner message.
    Rules: `cancel_invitation` R1 [BUG-1986]"""
    mk_member(ub)
    j = mk_invitation("J", t.ED, workspace_id=w2.id)
    before_j = snap_before(db, j)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=j.id, canceller_id=ub.id, canceller_role="member", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert snap(db, j) == before_j
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-22
@BUG_1986
def test_wsmg_xi_22__a_non_owner_asking_about_an_accepted_invitation_gets_the_owner_message(
    db, t, w1, ub, mk_member, mk_invitation,
):
    """WSMG-XI-22 — a non-owner asking about an accepted invitation gets the owner message.
    Rules: `cancel_invitation` R1 [BUG-1986]"""
    mk_member(ub)
    i = mk_invitation("I", t.ED, status="accepted")
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=ub.id, canceller_role="member", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-23
def test_wsmg_xi_23__owner_of_an_earlier_workspace_member_here_may_not_cancel(
    db, t, w0, w1, ub, mk_member, mk_invitation,
):
    """WSMG-XI-23 — owner of an earlier workspace, member here: may not cancel.
    Rules: `cancel_invitation` R1 (grant held in another workspace)"""
    mk_member(ub, workspace_id=w0.id, role="owner")
    mk_member(ub)
    i = mk_invitation("I", t.ED)
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=ub.id, canceller_role="member", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-24
def test_wsmg_xi_24__owner_of_a_later_workspace_member_here_may_not_cancel(
    db, t, w1, w2, ub, mk_member, mk_invitation,
):
    """WSMG-XI-24 — owner of a later workspace, member here: may not cancel.
    Rules: `cancel_invitation` R1 (grant held in another workspace)"""
    mk_member(ub)
    i = mk_invitation("I", t.ED)
    mk_member(ub, workspace_id=w2.id, role="owner")
    before_i = snap_before(db, i)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.cancel_invitation(db, invitation_id=i.id, canceller_id=ub.id, canceller_role="member", workspace_id=w1.id)
    # Then 2
    assert str(exc.value) == "Only the workspace owner can cancel invitations"
    # Then 3
    assert snap(db, i) == before_i
    # Then 4
    assert written(db) == before


# [claude] WSMG-XI-25
def test_wsmg_xi_25__cancel_flushes_and_never_commits(db, t, w1, uo, mk_invitation):
    """WSMG-XI-25 — cancel flushes and never commits.
    Rules: `cancel_invitation` Side effects"""
    i = mk_invitation("I", t.ED)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.cancel_invitation(
            db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id,
        )

    # Then 1
    row = reread(db, i)
    assert row.status == "cancelled"
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    row = reread(db, i)
    assert row.status == "pending"
    # Then 4
    assert result is None


# [claude] WSMG-XI-26
@BUG_1404
def test_wsmg_xi_26__the_audit_row_carries_the_request_s_ip_address_and_user_agent(db, t, w1, uo, mk_invitation):
    """WSMG-XI-26 — the audit row carries the request's IP address and user agent.
    Rules: A2 [BUG-1404]; `cancel_invitation` R6"""
    i = mk_invitation("I", t.ED)

    M.cancel_invitation(
        db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id,
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test",
    )

    # Then 1
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 2
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 Test"


# [claude] WSMG-XI-27
def test_wsmg_xi_27__the_audit_row_carries_the_invitation_s_email_exactly_as_stored(db, t, w1, uo, mk_invitation):
    """WSMG-XI-27 — the audit row carries the invitation's email exactly as stored, capitals kept.
    Rules: `cancel_invitation` R6"""
    i = mk_invitation("I", f"Dan.{t.TAG}@Acme.com")

    result = M.cancel_invitation(db, invitation_id=i.id, canceller_id=uo.id, canceller_role="owner", workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, i)
    assert row.status == "cancelled"
    assert row.email == f"Dan.{t.TAG}@Acme.com"
    # Then 3
    rows = audit(db, w1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"invitation_id": i.id, "email": f"Dan.{t.TAG}@Acme.com"}


# --------------------------------------------------------------------------- #
# Pending the payment portal — OQ-16 (create_workspace_with_owner R1).
# Today's behaviour: a new workspace may start on any active plan, unpaid.
# Only these cards change when the portal decides.
# --------------------------------------------------------------------------- #

# [claude] WSMG-P16-01
def test_wsmg_p16_01__an_active_non_default_plan_asked_for_at_creation_is_used_unpaid(db, t, ua, mk_plan):
    """WSMG-P16-01 — an active non-default plan asked for at creation is used, unpaid.
    Rules: `create_workspace_with_owner` R1 (pending OQ-16)"""
    mk_plan("PD")
    px = mk_plan("PX")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=px.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == px.id
    # Then 3
    rows = audit(db, result)
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {"plan": f"pro-{t.TAG}"}


# [claude] WSMG-P16-02
def test_wsmg_p16_02__the_unlimited_enterprise_plan_can_be_picked_and_still_starts_a_trial(db, t, ua, mk_plan):
    """WSMG-P16-02 — the unlimited enterprise plan can be picked at creation and still starts a trial.
    Rules: `create_workspace_with_owner` R1 (pending OQ-16), R6"""
    mk_plan("PD")
    pe = mk_plan("PE")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=pe.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pe.id
    # Then 3
    row = reread(db, result)
    assert row.subscription_status == "trial"
    assert row.trial_ends_at == NOW + timedelta(days=14)


# [claude] WSMG-P16-03
def test_wsmg_p16_03__the_default_plan_s_own_id_given_explicitly_is_used(db, t, ua, mk_plan):
    """WSMG-P16-03 — the default plan's own id given explicitly is used.
    Rules: `create_workspace_with_owner` R1 (pending OQ-16)"""
    mk_plan("PX")
    pd = mk_plan("PD")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=pd.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == pd.id


# [claude] WSMG-P16-04
def test_wsmg_p16_04__an_explicit_active_plan_works_with_no_default_plan_at_all(db, t, ua, mk_plan):
    """WSMG-P16-04 — an explicit active plan works with no default plan at all.
    Rules: `create_workspace_with_owner` R1 (pending OQ-16), R3"""
    px = mk_plan("PX")

    result = M.create_workspace_with_owner(
        db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=t.SL), owner_user_id=ua.id, subscription_plan_id=px.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.subscription_plan_id == px.id


# --------------------------------------------------------------------------- #
# Pending the plans/subscriptions design — OQ-17 / BUG-1989 (max_members = 0).
# Today's behaviour; only these cards change when the design settles what 0 means.
# --------------------------------------------------------------------------- #

# [claude] WSMG-P17-01
def test_wsmg_p17_01__a_limit_of_0_today_means_no_limit_the_owner_alone_one_more_is_added(db, w1, uo, ua, set_limit):
    """WSMG-P17-01 — a limit of 0 today means no limit: the owner alone, one more is added.
    Rules: `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)"""
    set_limit(0)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.status == "active"
    # Then 3
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 2


# [claude] WSMG-P17-02
def test_wsmg_p17_02__a_limit_of_0_today_means_no_limit_a_fifth_active_member_is_added(
    db, w1, uo, ua, ub, uc, mk_member, set_limit,
):
    """WSMG-P17-02 — a limit of 0 today means no limit: a fifth active member is added.
    Rules: `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)"""
    set_limit(0)
    mk_member(ub)
    mk_member(uc)
    p1 = make_profile(db)
    mk_member(p1)

    result = M.add_member_to_workspace(db, workspace_id=w1.id, user_id=ua.id, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 5


# [claude] WSMG-P17-03
def test_wsmg_p17_03__a_limit_of_0_today_means_no_limit_the_owner_alone_may_invite(db, t, w1, uo, set_limit):
    """WSMG-P17-03 — a limit of 0 today means no limit: the owner alone may invite.
    Rules: `create_invitation` R9 (pending BUG-1989 / OQ-17)"""
    set_limit(0)

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(invitations(db, w1, status="pending")) == 1


# [claude] WSMG-P17-04
def test_wsmg_p17_04__a_limit_of_0_today_means_no_limit_invited_on_top_of_members_and_invitations(
    db, t, w1, uo, ub, uc, mk_member, mk_invitation, set_limit,
):
    """WSMG-P17-04 — a limit of 0 today means no limit: invited on top of members and pending invitations.
    Rules: `create_invitation` R9 (pending BUG-1989 / OQ-17)"""
    set_limit(0)
    mk_member(ub)
    mk_member(uc)
    mk_invitation("J", t.ED)
    mk_invitation("K", f"fay.{t.TAG}@acme.com")

    result = M.create_invitation(db, workspace_id=w1.id, email=t.EE, role="member", inviter_id=uo.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(invitations(db, w1, status="pending")) == 3


# [claude] WSMG-P17-05
def test_wsmg_p17_05__a_limit_of_0_today_means_no_limit_an_invitation_is_accepted(
    db, t, w1, ua, ub, mk_member, mk_invitation, set_limit,
):
    """WSMG-P17-05 — a limit of 0 today means no limit: an invitation is accepted.
    Rules: `accept_invitation` R3; `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)"""
    set_limit(0)
    mk_member(ub)
    i = mk_invitation("I", t.EA)

    result = M.accept_invitation(db, invitation_id=i.id, user_id=ua.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, "workspace_members", workspace_id=w1.id, status="active") == 3
    # Then 3
    row = reread(db, i)
    assert row.status == "accepted"
