"""Unit tests for app/dao/subscription_plan.py.

Implements tests/unit/dao/subscription_plan.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.subscription_plan import subscription_plan_dao
from app.models.subscription_plan import SubscriptionPlan
from tests.unit.factories import make_subscription_plan

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton subscription_plan_dao" (a module-level name, not a fixture)
dao = subscription_plan_dao


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one()


# Convention "nothing written": the number of `subscription_plans` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(SubscriptionPlan.__table__))


# The `count:` lines: SELECT count(*) through db.scalar(text(...)), with the filter stated
def count_rows(db, table, **filters):
    where = " AND ".join(f"{column} = :{column}" for column in filters) or "TRUE"
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {where}"), filters)


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


# --------------------------------------------------------------------------- #
# SubscriptionPlanDAO.get_default_plan
# --------------------------------------------------------------------------- #


# [claude] SBP-GD-01
def test_sbp_gd_01__returns_the_active_default_plan_not_the_first_plan(db):
    """SBP-GD-01 — returns the active default plan, not the first plan.
    Rules: `get_default_plan` R1, Returns"""
    make_subscription_plan(db, name="Starter")
    b = make_subscription_plan(db, name="Free", is_default=True)

    result = dao.get_default_plan(db)

    # Then 1
    assert isinstance(result, SubscriptionPlan)
    # Then 2
    assert result.id == b.id
    # Then 3
    assert result.name == "Free"
    # Then 4
    assert result.is_default is True
    assert result.is_active is True


# [claude] SBP-GD-02
def test_sbp_gd_02__the_only_active_plan_is_not_returned_when_it_is_not_the_default(db):
    """SBP-GD-02 — the only active plan is not returned when it is not the default.
    Rules: `get_default_plan` R2"""
    make_subscription_plan(db, name="Starter")

    result = dao.get_default_plan(db)

    # Then 1
    assert result is None


# [claude] SBP-GD-03
def test_sbp_gd_03__an_inactive_default_is_passed_over_for_the_active_one(db):
    """SBP-GD-03 — an inactive default is passed over for the active one.
    Rules: `get_default_plan` R3"""
    make_subscription_plan(db, name="Old", is_default=True, is_active=False)
    b = make_subscription_plan(db, name="Free", is_default=True)

    result = dao.get_default_plan(db)

    # Then 1
    assert result.id == b.id


# [claude] SBP-GD-04
def test_sbp_gd_04__an_inactive_default_alone_returns_none(db):
    """SBP-GD-04 — an inactive default alone returns None.
    Rules: `get_default_plan` R3"""
    make_subscription_plan(db, name="Old", is_default=True, is_active=False)

    result = dao.get_default_plan(db)

    # Then 1
    assert result is None


# [claude] SBP-GD-05
def test_sbp_gd_05__no_plans_at_all_returns_none(db):
    """SBP-GD-05 — no plans at all returns None.
    Rules: `get_default_plan` R4"""

    result = dao.get_default_plan(db)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db, "subscription_plans") == 0


# [claude] SBP-GD-06
def test_sbp_gd_06__plans_but_no_active_default_return_none(db):
    """SBP-GD-06 — plans, but no active default, return None.
    Rules: `get_default_plan` R4"""
    a = make_subscription_plan(db, name="Starter")
    b = make_subscription_plan(db, name="Old", is_default=True, is_active=False)
    before_a = snap(db, a)
    before_b = snap(db, b)

    result = dao.get_default_plan(db)

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] SBP-GD-07
@pytest.mark.xfail(strict=True, reason="BUG-1224: Nothing stops two default plans")
def test_sbp_gd_07__a_second_active_default_is_refused(db):
    """SBP-GD-07 — a second active default is refused.
    Rules: `get_default_plan` R5 [BUG-1224]"""
    a = make_subscription_plan(db, name="Free", is_default=True)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            make_subscription_plan(db, name="Pro", is_default=True)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "subscription_plans", is_default=True, is_active=True) == 1
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] SBP-GD-08
def test_sbp_gd_08__a_second_default_that_is_inactive_is_stored(db):
    """SBP-GD-08 — a second default that is inactive is stored.
    Rules: `get_default_plan` R5"""
    a = make_subscription_plan(db, name="Free", is_default=True)
    before_a = snap(db, a)

    result = make_subscription_plan(db, name="Old", is_default=True, is_active=False)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_default is True
    assert row.is_active is False
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] SBP-GD-09
def test_sbp_gd_09__a_plan_that_is_not_the_default_is_stored_next_to_the_default(db):
    """SBP-GD-09 — a plan that is not the default is stored next to the default.
    Rules: `get_default_plan` R5"""
    a = make_subscription_plan(db, name="Free", is_default=True)
    before_a = snap(db, a)

    result = make_subscription_plan(db, name="Pro")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_default is False
    assert row.is_active is True
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] SBP-GD-10
def test_sbp_gd_10__writes_nothing_a_pending_default_stays_pending_and_is_not_returned(db):
    """SBP-GD-10 — writes nothing: a pending default stays pending and is not returned.
    Rules: `get_default_plan` R4, Side effects"""
    a = make_subscription_plan(db, name="Starter")
    p = SubscriptionPlan(name="Pending", display_name="Pending", is_default=True, is_active=True)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_default_plan(db)
    written = recorder.written()

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert stored_count(db) == before
    # Then 6
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 7
    assert written == []


# [claude] SBP-GD-11
def test_sbp_gd_11__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db):
    """SBP-GD-11 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_default_plan` Side effects"""
    a = make_subscription_plan(db, name="Free", is_default=True)
    p = SubscriptionPlan(name="Pending", display_name="Pending")
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_default_plan(db)
    written = recorder.written()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert stored_count(db) == before
    # Then 5
    assert written == []


# [claude] SBP-GD-12
def test_sbp_gd_12__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db):
    """SBP-GD-12 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_default_plan` Side effects"""
    a = make_subscription_plan(db, name="Free", is_default=True)
    b = make_subscription_plan(db, name="Starter")
    b.display_name = "Edited"

    result = dao.get_default_plan(db)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
