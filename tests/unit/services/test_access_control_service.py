"""Unit tests for app/services/access_control_service.py.

Implements tests/unit/services/access_control_service.cases.md (revision 5), one
test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Patched, as Conventions name
them: the failing commit / refresh / DAO create wraps and the commit / rollback
spies (the spies still call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment; `# Then N` marks the checks of the card's Then line N. Write cards of
the owner go through `call_uid`, which adds `user_id` only once the service's
signature has it (BUG-1875).
"""

# ruff: noqa: SIM117  (Conventions prescribe the nested `with`)
from contextlib import contextmanager
from inspect import Parameter, signature
from unittest.mock import patch

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import DataError

from app.core.exceptions import PermissionDeniedError
from app.models.access_control import AccessControl
from app.models.enums import AccessControlTypeEnum, RoleEnum
from app.models.workspace_member import WorkspaceMember
from app.schemas.access_control import AccessControlCreate, AccessControlUpdate
from app.services.access_control_service import access_control_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = access_control_service

OWNER = RoleEnum.OWNER
FINANCE = RoleEnum.FINANCE
GT = RoleEnum.GROUND_TEAM
PAGE = AccessControlTypeEnum.PAGE
FEATURE = AccessControlTypeEnum.FEATURE

MISSING = 999999999
DENY = "Only the workspace owner can change access control"

BUG_1875 = "BUG-1875: Any member can change the workspace's permission table"
BUG_2255 = "BUG-2255: Filtering permission rows by role and type ignores the type"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
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
def ua(db, w2):
    return make_profile(db, name="Ana")


@pytest.fixture
def uo(db, ua):
    return make_profile(db, name="Omar")


@pytest.fixture
def uz(db, uo):
    return make_profile(db, name="Zara")


@pytest.fixture
def mo(db, w1, uo, uz):
    return _add(
        db,
        WorkspaceMember(
            workspace_id=w1.id, user_id=uo.id, role="owner", status="active"
        ),
    )


@pytest.fixture(autouse=True)
def standing_rows(mo):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "rule"; "but" overrides columns
@pytest.fixture
def rule(db, w1):
    def _mk(**but):
        fields = {
            "workspace_id": w1.id,
            "type": PAGE,
            "target": "/orders",
            "role": OWNER,
        }
        fields.update(but)
        return _add(db, AccessControl(**fields))

    return _mk


# Convention "mem(U, role, status='active', ws=W1)"
@pytest.fixture
def mem(db, w1):
    def _mk(u, role, status="active", ws=None):
        ws = ws or w1
        return _add(
            db,
            WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=status),
        )

    return _mk


def add_101(db, w1):
    db.add_all(
        [
            AccessControl(workspace_id=w1.id, type=PAGE, target=f"/p{i}", role=OWNER)
            for i in range(101)
        ]
    )
    db.flush()


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra row X" / "pending P" (after the commit point, not committed)
def add_extra(db, w2, target="extra"):
    return _add(
        db, AccessControl(workspace_id=w2.id, type=FEATURE, target=target, role=FINANCE)
    )


def x_gone(db, x_id):
    return (
        db.scalar(
            select(func.count())
            .select_from(AccessControl)
            .where(AccessControl.id == x_id)
        )
        == 0
    )


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def reread(db, row_id):
    db.expire_all()
    return db.get(AccessControl, row_id)


def snap(db, row_id):
    row = db.get(AccessControl, row_id)
    return (row.type, row.target, row.role, row.workspace_id)


def unchanged(db, row_id, before):
    db.expire_all()
    return snap(db, row_id) == before


def ws_count(db, ws_id):
    return db.scalar(
        select(func.count())
        .select_from(AccessControl)
        .where(AccessControl.workspace_id == ws_id)
    )


def counts(db, w0, w1, w2):
    return (ws_count(db, w0.id), ws_count(db, w1.id), ws_count(db, w2.id))


def idset(r):
    return {c.id for c in r}


@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


@contextmanager
def failing_dao_create(db):
    with (
        patch(
            "app.services.access_control_service.access_control_dao.create",
            side_effect=RuntimeError("dao boom"),
        ),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


def call_uid(db, fn, u, **kw):
    """Convention call_uid(fn, U, **kw): adds user_id only once the signature has it."""
    if "user_id" in signature(fn).parameters:
        return fn(db, **kw, user_id=u.id)
    return fn(db, **kw)


# =========================================================================== #
# get_controls
# =========================================================================== #


# [claude] ACS-L-01
def test_acs_l_01__role_only_returns_that_roles_rows(db, w0, w1, w2, rule):
    """ACS-L-01 — role only: that role's rows of the workspace, every type.
    Rules: get_controls R1."""
    rule(workspace_id=w0.id)
    a1 = rule()
    a2 = rule(type=FEATURE, target="reports")
    rule(role=FINANCE)
    rule(workspace_id=w2.id)
    result = svc.get_controls(db, workspace_id=w1.id, role=OWNER, limit=1000)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a1.id, a2.id}


# [claude] ACS-L-02
@pytest.mark.xfail(strict=True, reason=BUG_2255)
def test_acs_l_02__role_and_type_together(db, w1, rule):
    """ACS-L-02 — role and type together: only rows matching both.
    Rules: get_controls R1 [BUG-2255]."""
    rule()
    af = rule(type=FEATURE, target="reports")
    rule(type=FEATURE, target="reports", role=FINANCE)
    result = svc.get_controls(
        db, workspace_id=w1.id, role=OWNER, access_type=FEATURE, limit=1000
    )
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {af.id}


# [claude] ACS-L-03
@pytest.mark.xfail(strict=True, reason=BUG_2255)
def test_acs_l_03__hidden_row_takes_no_place_before_skip(db, w1, rule):
    """ACS-L-03 — role and type together: a hidden row ahead of the skipped row takes no place.
    Rules: get_controls R1 [BUG-2255]."""
    rule()
    rule(type=FEATURE, target="a")
    f2 = rule(type=FEATURE, target="b")
    result = svc.get_controls(
        db, workspace_id=w1.id, role=OWNER, access_type=FEATURE, skip=1, limit=10
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert idset(result) == {f2.id}


# [claude] ACS-L-04
def test_acs_l_04__type_only_every_role(db, w0, w1, w2, rule):
    """ACS-L-04 — type only: that type's rows of the workspace, every role.
    Rules: get_controls R2."""
    rule(workspace_id=w0.id, type=FEATURE)
    fa = rule(type=FEATURE)
    fb = rule(type=FEATURE, role=FINANCE)
    rule()
    rule(workspace_id=w2.id, type=FEATURE)
    result = svc.get_controls(db, workspace_id=w1.id, access_type=FEATURE, limit=1000)
    # Then 1
    assert idset(result) == {fa.id, fb.id}


# [claude] ACS-L-05
def test_acs_l_05__neither_filter_every_row_of_the_workspace(db, w0, w1, w2, rule):
    """ACS-L-05 — neither filter: every row of the workspace, not W0's or W2's.
    Rules: get_controls R3."""
    rule(workspace_id=w0.id)
    a1 = rule()
    a2 = rule(type=FEATURE, role=FINANCE)
    rule(workspace_id=w2.id)
    result = svc.get_controls(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert idset(result) == {a1.id, a2.id}


# [claude] ACS-L-06
def test_acs_l_06__neither_filter_default_limit_100(db, w1):
    """ACS-L-06 — neither filter: the default limit is 100.
    Rules: get_controls R3, R4."""
    add_101(db, w1)
    result = svc.get_controls(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100


# [claude] ACS-L-07
def test_acs_l_07__role_only_default_limit_100(db, w1):
    """ACS-L-07 — role only: the default limit is 100.
    Rules: get_controls R1, R4."""
    add_101(db, w1)
    result = svc.get_controls(db, workspace_id=w1.id, role=OWNER)
    # Then 1
    assert len(result) == 100


# [claude] ACS-L-08
def test_acs_l_08__type_only_default_limit_100(db, w1):
    """ACS-L-08 — type only: the default limit is 100.
    Rules: get_controls R2, R4."""
    add_101(db, w1)
    result = svc.get_controls(db, workspace_id=w1.id, access_type=PAGE)
    # Then 1
    assert len(result) == 100


# [claude] ACS-L-09
def test_acs_l_09__skip_and_limit_passed_on(db, w1, rule):
    """ACS-L-09 — skip and limit are passed on.
    Rules: get_controls R4."""
    a = rule(target="/a")
    b = rule(target="/b")
    c = rule(target="/c")
    result = svc.get_controls(db, workspace_id=w1.id, role=OWNER, skip=1, limit=1)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert idset(result) <= {a.id, b.id, c.id}


# [claude] ACS-L-10
def test_acs_l_10__limit_1000_returns_all_101(db, w1):
    """ACS-L-10 — limit 1000 returns all 101.
    Rules: get_controls R4."""
    add_101(db, w1)
    result = svc.get_controls(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert len(result) == 101


# [claude] ACS-L-11
def test_acs_l_11__negative_skip_fails_in_the_database(db, w1, rule):
    """ACS-L-11 — a negative skip fails in the database.
    Rules: get_controls R4."""
    rule()
    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            svc.get_controls(db, workspace_id=w1.id, skip=-1)


# [claude] ACS-L-12
def test_acs_l_12__read_neither_commits_nor_rolls_back(db, w1, w2, rule):
    """ACS-L-12 — a read neither commits nor rolls back; pending changes stay.
    Rules: get_controls R5; TX5."""
    b = rule()
    commit_point(db)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    b.target = "/edited"
    with spies(db) as (cm, rb):
        result = svc.get_controls(db, workspace_id=w1.id, role=OWNER, limit=1000)
    # Then 1
    assert b.id in idset(result)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(AccessControl, p_id) is p
    # Then 5
    assert b in db.dirty
    # Then 6
    assert b.target == "/edited"


# [claude] ACS-L-13
def test_acs_l_13__workspace_with_no_rows_gives_empty_list(db, w1, w2, rule):
    """ACS-L-13 — a workspace with no rows gives an empty list.
    Rules: get_controls R3."""
    rule(workspace_id=w2.id)
    result = svc.get_controls(db, workspace_id=w1.id)
    # Then 1
    assert result == []


# =========================================================================== #
# get_by_id
# =========================================================================== #


# [claude] ACS-G-01
def test_acs_g_01__returns_the_workspaces_row(db, w0, w1, w2, rule):
    """ACS-G-01 — returns the workspace's row.
    Rules: get_by_id R1."""
    rule(workspace_id=w0.id)
    a = rule()
    rule(workspace_id=w2.id)
    result = svc.get_by_id(db, control_id=a.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.target == "/orders"


# [claude] ACS-G-02
def test_acs_g_02__w0_row_is_none_in_w1(db, w0, w1, rule):
    """ACS-G-02 — W0's row (lower id) is None in W1.
    Rules: get_by_id R1."""
    a0 = rule(workspace_id=w0.id)
    rule()
    result = svc.get_by_id(db, control_id=a0.id, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] ACS-G-03
def test_acs_g_03__w2_row_is_none_in_w1(db, w1, w2, rule):
    """ACS-G-03 — W2's row (higher id) is None in W1.
    Rules: get_by_id R1."""
    rule()
    a9 = rule(workspace_id=w2.id)
    result = svc.get_by_id(db, control_id=a9.id, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] ACS-G-04
def test_acs_g_04__unknown_id_is_none(db, w1, rule):
    """ACS-G-04 — an unknown id is None.
    Rules: get_by_id R1."""
    rule()
    result = svc.get_by_id(db, control_id=MISSING, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] ACS-G-05
def test_acs_g_05__id_0_is_none(db, w1, rule):
    """ACS-G-05 — id 0 is None.
    Rules: get_by_id R1."""
    rule()
    result = svc.get_by_id(db, control_id=0, workspace_id=w1.id)
    # Then 1
    assert result is None


# [claude] ACS-G-06
def test_acs_g_06__get_neither_commits_nor_rolls_back(db, w1, w2, rule):
    """ACS-G-06 — a get neither commits nor rolls back; pending changes stay.
    Rules: get_by_id R2; TX5."""
    b = rule()
    commit_point(db)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    b.target = "/edited"
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, control_id=b.id, workspace_id=w1.id)
    # Then 1
    assert result is b
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert db.get(AccessControl, p_id) is p
    # Then 5
    assert b in db.dirty
    # Then 6
    assert b.target == "/edited"


# =========================================================================== #
# create_control
# =========================================================================== #


# [claude] ACS-C-01
def test_acs_c_01__creates_the_row_committed_and_reread(db, w0, w1, w2, uo):
    """ACS-C-01 — creates the row in the given workspace, committed and re-read.
    Rules: create_control R2, R3; TX1, TX2; R1 (caller UO through call_uid)."""
    commit_point(db)
    result = call_uid(
        db,
        svc.create_control,
        uo,
        control_in=AccessControlCreate(type=FEATURE, target="reports", role=FINANCE),
        workspace_id=w1.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    assert result.workspace_id == w1.id
    assert result.target == "reports"
    # Then 3
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    new_id = result.id
    db.rollback()
    # Then 4
    row = db.scalars(select(AccessControl).where(AccessControl.id == new_id)).one()
    assert row.workspace_id == w1.id
    assert row.type == FEATURE
    assert row.target == "reports"
    assert row.role == FINANCE
    # Then 5
    assert ws_count(db, w0.id) == 0
    assert ws_count(db, w2.id) == 0


# [claude] ACS-C-02
def test_acs_c_02__identical_row_and_blank_target_accepted(db, w1, uo, rule):
    """ACS-C-02 — an identical row and a blank target are both accepted.
    Rules: create_control R2 (D2); R1 (caller UO through call_uid)."""
    a = rule(target="")
    commit_point(db)
    result = call_uid(
        db,
        svc.create_control,
        uo,
        control_in=AccessControlCreate(type=PAGE, target="", role=OWNER),
        workspace_id=w1.id,
    )
    # Then 1
    assert result.id != a.id
    db.rollback()
    # Then 2
    n = db.scalar(
        select(func.count())
        .select_from(AccessControl)
        .where(
            AccessControl.workspace_id == w1.id,
            AccessControl.type == PAGE,
            AccessControl.target == "",
            AccessControl.role == OWNER,
        )
    )
    assert n == 2


# [claude] ACS-C-03
def test_acs_c_03__dao_error_rolls_back_and_reaches_caller(db, w0, w1, w2, uo):
    """ACS-C-03 — an error from the DAO rolls back, reaches the caller unchanged, and discards
    other pending changes.
    Rules: create_control R3; TX3; R1 (caller UO through call_uid)."""
    commit_point(db)
    before = counts(db, w0, w1, w2)
    x_id = add_extra(db, w2).id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_dao_create(db) as rb:
            call_uid(
                db,
                svc.create_control,
                uo,
                control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER),
                workspace_id=w1.id,
            )
    assert str(exc.value) == "dao boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert counts(db, w0, w1, w2) == before
    # Then 5
    assert (
        db.scalar(
            select(func.count())
            .select_from(AccessControl)
            .where(AccessControl.workspace_id == w1.id)
        )
        == 0
    )


# [claude] ACS-C-04
def test_acs_c_04__failing_commit_rolls_back(db, w0, w1, w2, uo):
    """ACS-C-04 — a failing commit rolls back and nothing is saved.
    Rules: create_control R3; TX3; R1 (caller UO through call_uid)."""
    commit_point(db)
    before = counts(db, w0, w1, w2)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            call_uid(
                db,
                svc.create_control,
                uo,
                control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER),
                workspace_id=w1.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-C-05
def test_acs_c_05__failing_refresh_leaves_row_saved(db, w1, uo):
    """ACS-C-05 — a failing re-read after the commit leaves the row saved.
    Rules: create_control R3; TX3 (as TC5); R1 (caller UO through call_uid)."""
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            call_uid(
                db,
                svc.create_control,
                uo,
                control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER),
                workspace_id=w1.id,
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = db.scalars(
        select(AccessControl).where(AccessControl.workspace_id == w1.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].target == "/orders"


def _refused_create(db, w0, w1, w2, user_id):
    """Shared body of the create refusal cards (C-07 ... C-22): the When and Then 1-5."""
    before = counts(db, w0, w1, w2)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        svc.create_control(
            db,
            control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER),
            workspace_id=w1.id,
            user_id=user_id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-C-07
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_07__ground_team_manager_may_not_create(db, w0, w1, w2, ua, mem):
    """ACS-C-07 — a ground-team-manager may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "ground-team-manager")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-08
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_08__finance_may_not_create(db, w0, w1, w2, uz, mem):
    """ACS-C-08 — a finance member may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "finance")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_09__ground_team_may_not_create(db, w0, w1, w2, ua, mem):
    """ACS-C-09 — a ground-team member may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "ground-team")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_10__manager_may_not_create(db, w0, w1, w2, uz, mem):
    """ACS-C-10 — a manager may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "manager")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_11__member_may_not_create(db, w0, w1, w2, ua, mem):
    """ACS-C-11 — a plain member may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "member")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-12
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_12__viewer_may_not_create(db, w0, w1, w2, uz, mem):
    """ACS-C-12 — a viewer may not create.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "viewer")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-13
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_13__capital_owner_is_not_owner(db, w0, w1, w2, ua, mem):
    """ACS-C-13 — role "Owner" (capital O) is not the owner.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "Owner")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-14
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_14__owner_with_trailing_space_is_not_owner(db, w0, w1, w2, uz, mem):
    """ACS-C-14 — role "owner " (trailing space) is not the owner.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "owner ")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-15
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_15__inactive_owner_refused(db, w0, w1, w2, ua, mem):
    """ACS-C-15 — an inactive owner row is refused.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "owner", status="inactive")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-16
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_16__suspended_owner_refused(db, w0, w1, w2, uz, mem):
    """ACS-C-16 — a suspended owner row is refused.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "owner", status="suspended")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-17
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_17__invited_owner_refused(db, w0, w1, w2, ua, mem):
    """ACS-C-17 — an invited owner row is refused.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "owner", status="invited")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-18
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_18__capital_active_is_not_active(db, w0, w1, w2, uz, mem):
    """ACS-C-18 — status "Active" (capital A) is not active.
    Rules: create_control R1 [BUG-1875]."""
    mem(uz, "owner", status="Active")
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-19
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_19__owner_of_w0_refused_in_w1(db, w0, w1, w2, ua, mem):
    """ACS-C-19 — the owner of W0 (row built first) is a ground-team member in W1: refused.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "owner", ws=w0)
    mem(ua, "ground-team")
    commit_point(db)
    _refused_create(db, w0, w1, w2, ua.id)


# [claude] ACS-C-20
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_20__owner_of_w2_refused_in_w1(db, w0, w1, w2, ua, uz, mem):
    """ACS-C-20 — the owner of W2 (row built after) with no W1 membership: refused.
    Rules: create_control R1 [BUG-1875]."""
    mem(ua, "ground-team")
    mem(uz, "owner", ws=w2)
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-21
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_21__owner_user_id_without_membership_refused(db, w0, w1, w2, uz):
    """ACS-C-21 — the person named by owner_user_id but with no membership row is refused.
    Rules: create_control R1 [BUG-1875]."""
    w1.owner_user_id = uz.id
    db.flush()
    commit_point(db)
    _refused_create(db, w0, w1, w2, uz.id)


# [claude] ACS-C-22
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_22__unknown_user_refused(db, w0, w1, w2):
    """ACS-C-22 — an unknown user is refused.
    Rules: create_control R1 [BUG-1875]."""
    commit_point(db)
    _refused_create(db, w0, w1, w2, MISSING)


# [claude] ACS-C-23
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_23__refusal_keeps_pending_row(db, w1, w2, ua, mem):
    """ACS-C-23 — a refusal neither commits nor rolls back: a pending row of the session survives.
    Rules: create_control R1 [BUG-1875] (raised before the try)."""
    mem(ua, "finance")
    commit_point(db)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(PermissionDeniedError) as exc:
            svc.create_control(
                db,
                control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER),
                workspace_id=w1.id,
                user_id=ua.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    assert db.get(AccessControl, p_id) is p
    # Then 8
    assert (
        db.scalar(
            select(func.count())
            .select_from(AccessControl)
            .where(AccessControl.id == p_id)
        )
        == 1
    )
    # Then 9
    assert ws_count(db, w1.id) == 0


# [claude] ACS-C-24
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_c_24__writers_take_keyword_only_user_id():
    """ACS-C-24 — the three writers take a required keyword-only user_id (signature alarm).
    Rules: create_control R1, update_control R1, delete_control R1 [BUG-1875]."""
    sigs = {
        name: signature(getattr(svc, name)).parameters
        for name in ("create_control", "update_control", "delete_control")
    }
    # Then 1
    assert sigs["create_control"]["user_id"].kind == Parameter.KEYWORD_ONLY
    # Then 2
    assert sigs["update_control"]["user_id"].kind == Parameter.KEYWORD_ONLY
    # Then 3
    assert sigs["delete_control"]["user_id"].kind == Parameter.KEYWORD_ONLY
    # Then 4
    assert sigs["create_control"]["user_id"].default is Parameter.empty
    # Then 5
    assert sigs["update_control"]["user_id"].default is Parameter.empty
    # Then 6
    assert sigs["delete_control"]["user_id"].default is Parameter.empty


# =========================================================================== #
# update_control
# =========================================================================== #


# [claude] ACS-U-01
def test_acs_u_01__changes_sent_field_keeps_others(db, w1, uo, rule):
    """ACS-U-01 — changes the sent field, keeps the others, committed and re-read.
    Rules: update_control R3, R4; TX1, TX2; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    result = call_uid(
        db,
        svc.update_control,
        uo,
        control_id=a_id,
        control_in=AccessControlUpdate(target="/sales"),
        workspace_id=w1.id,
    )
    # Then 1
    assert result.id == a_id
    # Then 2
    assert not (
        {c.key for c in inspect(result).mapper.column_attrs}
        & inspect(result).expired_attributes
    )
    db.rollback()
    # Then 3
    row = db.scalars(select(AccessControl).where(AccessControl.id == a_id)).one()
    assert row.target == "/sales"
    assert row.type == PAGE
    assert row.role == OWNER
    assert row.workspace_id == w1.id


# [claude] ACS-U-02
def test_acs_u_02__null_field_leaves_stored_value(db, w1, uo, rule):
    """ACS-U-02 — a null field leaves the stored value.
    Rules: update_control R3; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    result = call_uid(
        db,
        svc.update_control,
        uo,
        control_id=a_id,
        control_in=AccessControlUpdate(target=None, role=FINANCE),
        workspace_id=w1.id,
    )
    # Then 1
    assert result.id == a_id
    db.rollback()
    # Then 2
    row = db.scalars(select(AccessControl).where(AccessControl.id == a_id)).one()
    assert row.target == "/orders"
    assert row.role == FINANCE


# [claude] ACS-U-03
def test_acs_u_03__empty_update_changes_nothing_and_commits(db, w1, uo, rule):
    """ACS-U-03 — an empty update changes nothing and still commits.
    Rules: update_control R3; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    with spies(db) as (cm, _rb):
        result = call_uid(
            db,
            svc.update_control,
            uo,
            control_id=a_id,
            control_in=AccessControlUpdate(),
            workspace_id=w1.id,
        )
    # Then 1
    assert result.id == a_id
    # Then 2
    assert cm.call_count >= 1
    # Then 3
    assert unchanged(db, a_id, before)


# [claude] ACS-U-04
def test_acs_u_04__w0_row_answers_none(db, w0, w1, w2, uo, rule):
    """ACS-U-04 — W0's row (lower id) answers None, no commit, no rollback.
    Rules: update_control R2; TX4; R1 (caller UO through call_uid)."""
    a0 = rule(workspace_id=w0.id)
    a0_id = a0.id
    rule()
    commit_point(db)
    before = snap(db, a0_id)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    with spies(db) as (cm, rb):
        result = call_uid(
            db,
            svc.update_control,
            uo,
            control_id=a0_id,
            control_in=AccessControlUpdate(target="/sales"),
            workspace_id=w1.id,
        )
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.dirty
    # Then 5
    assert db.get(AccessControl, p_id) is p
    # Then 6
    assert unchanged(db, a0_id, before)


# [claude] ACS-U-05
def test_acs_u_05__w2_row_answers_none(db, w1, w2, uo, rule):
    """ACS-U-05 — W2's row (higher id) answers None.
    Rules: update_control R2; TX4; R1 (caller UO through call_uid)."""
    rule()
    a9 = rule(workspace_id=w2.id)
    a9_id = a9.id
    commit_point(db)
    before = snap(db, a9_id)
    result = call_uid(
        db,
        svc.update_control,
        uo,
        control_id=a9_id,
        control_in=AccessControlUpdate(target="/sales"),
        workspace_id=w1.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    assert unchanged(db, a9_id, before)


# [claude] ACS-U-06
def test_acs_u_06__unknown_id_answers_none(db, w1, uo, rule):
    """ACS-U-06 — an unknown id answers None.
    Rules: update_control R2; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    result = call_uid(
        db,
        svc.update_control,
        uo,
        control_id=MISSING,
        control_in=AccessControlUpdate(target="/sales"),
        workspace_id=w1.id,
    )
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    assert unchanged(db, a_id, before)


# [claude] ACS-U-07
def test_acs_u_07__failing_commit_rolls_back(db, w1, w2, uo, rule):
    """ACS-U-07 — a failing commit rolls back, discards other pending changes, saves nothing.
    Rules: update_control R4; TX3; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    x_id = add_extra(db, w2).id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            call_uid(
                db,
                svc.update_control,
                uo,
                control_id=a_id,
                control_in=AccessControlUpdate(target="/sales"),
                workspace_id=w1.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert unchanged(db, a_id, before)


# [claude] ACS-U-08
def test_acs_u_08__failing_refresh_leaves_change_saved(db, w1, uo, rule):
    """ACS-U-08 — a failing re-read after the commit leaves the change saved.
    Rules: update_control R4; TX3 (as TC5); R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            call_uid(
                db,
                svc.update_control,
                uo,
                control_id=a_id,
                control_in=AccessControlUpdate(target="/sales"),
                workspace_id=w1.id,
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    row = db.scalars(select(AccessControl).where(AccessControl.id == a_id)).one()
    assert row.target == "/sales"


# [claude] ACS-U-10
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_u_10__ground_team_manager_may_not_update(db, w1, uz, mem, rule):
    """ACS-U-10 — a ground-team-manager may not update.
    Rules: update_control R1 [BUG-1875]."""
    mem(uz, "ground-team-manager")
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        svc.update_control(
            db,
            control_id=a_id,
            control_in=AccessControlUpdate(target="/sales"),
            workspace_id=w1.id,
            user_id=uz.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged(db, a_id, before)


# [claude] ACS-U-11
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_u_11__non_owner_refused_before_lookup(db, w0, w1, w2, ua, mem, rule):
    """ACS-U-11 — a non-owner is refused before the lookup: an unknown id is 403, not None.
    Rules: update_control R1 [BUG-1875], R2."""
    mem(ua, "finance")
    rule()
    commit_point(db)
    before = counts(db, w0, w1, w2)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        svc.update_control(
            db,
            control_id=MISSING,
            control_in=AccessControlUpdate(target="/sales"),
            workspace_id=w1.id,
            user_id=ua.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert not db.dirty
    # Then 5
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-U-12
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_u_12__owner_of_w2_refused_on_w1_row(db, w1, w2, uz, mem, rule):
    """ACS-U-12 — the owner of W2 asking about W1's row is refused.
    Rules: update_control R1 [BUG-1875]."""
    mem(uz, "ground-team")
    mem(uz, "owner", ws=w2)
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        svc.update_control(
            db,
            control_id=a_id,
            control_in=AccessControlUpdate(target="/sales"),
            workspace_id=w1.id,
            user_id=uz.id,
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert not db.dirty
    # Then 5
    assert unchanged(db, a_id, before)


# [claude] ACS-U-13
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_u_13__update_refusal_keeps_pending_row(db, w1, w2, ua, mem, rule):
    """ACS-U-13 — an update refusal neither commits nor rolls back: a pending row of the
    session survives.
    Rules: update_control R1 [BUG-1875] (raised before the try)."""
    mem(ua, "finance")
    a = rule()
    a_id = a.id
    commit_point(db)
    before = snap(db, a_id)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(PermissionDeniedError) as exc:
            svc.update_control(
                db,
                control_id=a_id,
                control_in=AccessControlUpdate(target="/sales"),
                workspace_id=w1.id,
                user_id=ua.id,
            )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    assert db.get(AccessControl, p_id) is p
    # Then 8
    assert (
        db.scalar(
            select(func.count())
            .select_from(AccessControl)
            .where(AccessControl.id == p_id)
        )
        == 1
    )
    # Then 9
    assert unchanged(db, a_id, before)


# =========================================================================== #
# delete_control
# =========================================================================== #


# [claude] ACS-D-01
def test_acs_d_01__deletes_the_row_returns_true(db, w1, uo, rule):
    """ACS-D-01 — deletes the row, committed, returns True.
    Rules: delete_control R3; TX1, TX2; R1 (caller UO through call_uid)."""
    a = rule()
    b = rule(target="/b")
    a_id, b_id = a.id, b.id
    commit_point(db)
    result = call_uid(db, svc.delete_control, uo, control_id=a_id, workspace_id=w1.id)
    # Then 1
    assert result is True
    db.rollback()
    # Then 2
    assert (
        db.scalars(select(AccessControl).where(AccessControl.id == a_id)).first()
        is None
    )
    # Then 3
    assert (
        db.scalars(select(AccessControl).where(AccessControl.id == b_id)).first()
        is not None
    )


# [claude] ACS-D-02
def test_acs_d_02__w0_row_answers_false(db, w0, w1, w2, uo, rule):
    """ACS-D-02 — W0's row (lower id) answers False, no commit, no rollback.
    Rules: delete_control R2; TX4; R1 (caller UO through call_uid)."""
    a0 = rule(workspace_id=w0.id)
    rule()
    commit_point(db)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    with spies(db) as (cm, rb):
        result = call_uid(
            db, svc.delete_control, uo, control_id=a0.id, workspace_id=w1.id
        )
    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.deleted
    # Then 5
    assert db.get(AccessControl, p_id) is p
    # Then 6
    assert ws_count(db, w0.id) == 1
    # Then 7
    assert ws_count(db, w1.id) == 1


# [claude] ACS-D-03
def test_acs_d_03__w2_row_answers_false(db, w0, w1, w2, uo, rule):
    """ACS-D-03 — W2's row (higher id) answers False.
    Rules: delete_control R2; TX4; R1 (caller UO through call_uid)."""
    rule()
    a9 = rule(workspace_id=w2.id)
    commit_point(db)
    before = counts(db, w0, w1, w2)
    result = call_uid(db, svc.delete_control, uo, control_id=a9.id, workspace_id=w1.id)
    # Then 1
    assert result is False
    # Then 2
    assert not db.deleted
    # Then 3
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-D-04
def test_acs_d_04__unknown_id_answers_false(db, w0, w1, w2, uo, rule):
    """ACS-D-04 — an unknown id answers False.
    Rules: delete_control R2; R1 (caller UO through call_uid)."""
    rule()
    commit_point(db)
    before = counts(db, w0, w1, w2)
    result = call_uid(
        db, svc.delete_control, uo, control_id=MISSING, workspace_id=w1.id
    )
    # Then 1
    assert result is False
    # Then 2
    assert not db.deleted
    # Then 3
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-D-05
def test_acs_d_05__failing_commit_keeps_the_row(db, w1, w2, uo, rule):
    """ACS-D-05 — a failing commit rolls back; the row stays and pending changes are discarded.
    Rules: delete_control R4; TX3; R1 (caller UO through call_uid)."""
    a = rule()
    a_id = a.id
    commit_point(db)
    x_id = add_extra(db, w2).id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            call_uid(db, svc.delete_control, uo, control_id=a_id, workspace_id=w1.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    row = reread(db, a_id)
    assert row is not None
    assert row.target == "/orders"


def _refused_delete(db, w0, w1, w2, control_id, user_id):
    """Shared body of the delete refusal cards (D-07 ... D-09): the When and Then 1-5."""
    before = counts(db, w0, w1, w2)
    # Then 1
    with pytest.raises(PermissionDeniedError) as exc:
        svc.delete_control(
            db, control_id=control_id, workspace_id=w1.id, user_id=user_id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert not db.deleted
    # Then 5
    assert counts(db, w0, w1, w2) == before


# [claude] ACS-D-07
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_d_07__ground_team_may_not_delete(db, w0, w1, w2, ua, mem, rule):
    """ACS-D-07 — a ground-team member may not delete.
    Rules: delete_control R1 [BUG-1875]."""
    mem(ua, "ground-team")
    a = rule()
    commit_point(db)
    _refused_delete(db, w0, w1, w2, a.id, ua.id)


# [claude] ACS-D-08
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_d_08__viewer_refused_before_lookup(db, w0, w1, w2, uz, mem, rule):
    """ACS-D-08 — a viewer is refused before the lookup: an unknown id is 403, not False.
    Rules: delete_control R1 [BUG-1875], R2."""
    mem(uz, "viewer")
    rule()
    commit_point(db)
    _refused_delete(db, w0, w1, w2, MISSING, uz.id)


# [claude] ACS-D-09
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_d_09__owner_of_w0_refused_in_w1(db, w0, w1, w2, ua, mem, rule):
    """ACS-D-09 — the owner of W0 (row built first) is refused in W1.
    Rules: delete_control R1 [BUG-1875]."""
    mem(ua, "owner", ws=w0)
    mem(ua, "member")
    a = rule()
    commit_point(db)
    _refused_delete(db, w0, w1, w2, a.id, ua.id)


# [claude] ACS-D-10
@pytest.mark.xfail(strict=True, reason=BUG_1875)
def test_acs_d_10__delete_refusal_keeps_pending_row(db, w1, w2, ua, mem, rule):
    """ACS-D-10 — a delete refusal neither commits nor rolls back: a pending row of the
    session survives.
    Rules: delete_control R1 [BUG-1875] (raised before the try)."""
    mem(ua, "finance")
    a = rule()
    a_id = a.id
    commit_point(db)
    p = add_extra(db, w2, target="pending")
    p_id = p.id
    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(PermissionDeniedError) as exc:
            svc.delete_control(db, control_id=a_id, workspace_id=w1.id, user_id=ua.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == DENY
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    assert db.get(AccessControl, p_id) is p
    # Then 8
    assert (
        db.scalar(
            select(func.count())
            .select_from(AccessControl)
            .where(AccessControl.id == p_id)
        )
        == 1
    )
    # Then 9
    assert ws_count(db, w1.id) == 1
